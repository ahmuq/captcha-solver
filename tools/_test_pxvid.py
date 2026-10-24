#!/usr/bin/env python3
"""Uji hipotesis inti: apakah iframe PX butuh cookie `_pxvid` milik caller?

Alur (memakai teknik yang sudah terbukti):
  1. Luncurkan browser DENGAN --remote-debugging-port (CDP aktif, gate tidak relevan
     karena kita belum membuka challenge).
  2. Suntikkan cookie `_pxvid` (dan pxcts) milik bot lewat CDP Network.setCookie.
     Browser sendiri yang mengenkripsi, jadi tidak perlu tahu kunci os_crypt.
  3. Tutup dengan SIGTERM supaya store di-flush.
  4. Luncurkan ulang TANPA --remote-debugging-* (syarat gate mau render), buka challenge
     iframe, screenshot.

Bila gate render -> hipotesis terbukti dan ini jadi jalur produksi.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser, browser_binary   # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
SID = sys.argv[1] if len(sys.argv) > 1 else "c47b4333737040d896672da5593e77a5"
PXVID = sys.argv[2] if len(sys.argv) > 2 else ""
PORT = 9341
PROFILE = f"/tmp/_pxvid_{int(time.time())}"
shutil.rmtree(PROFILE, ignore_errors=True)


def cdp_set_cookies(port, cookies, timeout=25.0):
    """Suntikkan cookie lewat CDP; browser yang mengenkripsi ke store-nya."""
    ver = None
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                        timeout=3) as r:
                ver = json.load(r)
                break
        except Exception:
            continue
    if not ver:
        return False, "CDP tidak naik"

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        pages = [t for t in json.load(r) if t.get("type") == "page"]
    if not pages:
        return False, "tidak ada target page"

    from websockets.sync.client import connect
    ok = 0
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
        i = 1
        for name, value in cookies.items():
            if not value:
                continue
            sock.send(json.dumps({"id": i, "method": "Network.setCookie", "params": {
                "name": name, "value": value, "domain": ".hsprotect.net",
                "path": "/", "secure": True, "httpOnly": False,
                "expires": time.time() + 3600}}))
            while True:
                msg = json.loads(sock.recv())
                if msg.get("id") == i:
                    if (msg.get("result") or {}).get("success"):
                        ok += 1
                    break
            i += 1
    return True, f"{ok} cookie tersuntik"


print(f"profil: {PROFILE}")
print(f"session_id: {SID}")

# --- langkah 1: launch dengan CDP untuk menyuntik cookie ---
args = [browser_binary(), f"--user-data-dir={PROFILE}", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=0,0", "https://example.com"]
proc = subprocess.Popen(args, stdout=open("/tmp/_pxvid_inject.log", "w"),
                        stderr=subprocess.STDOUT,
                        env={**os.environ, "DISPLAY": ":99"})
time.sleep(12)

cookies = {"_pxvid": PXVID}
res = cdp_set_cookies(PORT, cookies)
print("suntik:", res)

# --- langkah 2: tutup bersih supaya store di-flush ---
subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
try:
    proc.wait(timeout=15)
except Exception:
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
time.sleep(3)

# --- langkah 3: verifikasi cookie benar-benar ada di store ---
from perimeterx.browser import harvest_cookies   # noqa: E402

har = harvest_cookies(PROFILE)
got = (har.get("cookies") or {}).get("_pxvid")
print(f"verifikasi store: _pxvid={got!r} (total cookie={har.get('total')})")
if got != PXVID:
    print("PERINGATAN: cookie tidak tersimpan — uji render tetap jalan untuk kontrol")

# --- langkah 4: buka challenge iframe TANPA protokol otomasi ---
url = f"https://iframe.hsprotect.net/index.html?app_id=PXzC5j78di&session_id={SID}"
br = Browser(PROFILE, proxy=PROXY)
try:
    br.start(url, 20.0)
    wid = br.window_id()
    title = br.title(wid) if wid else ""
    print(f"title: {title!r}")
    shot = f"/tmp/_pxvid_gate_{int(time.time())}.png"
    if wid and br.screenshot(shot, wid):
        sd = subprocess.run(["convert", shot, "-colorspace", "Gray", "-format",
                             "%[fx:standard_deviation]", "info:"],
                            capture_output=True, text=True).stdout.strip()
        print(f"screenshot: {shot}  (std-dev={sd}; blank ~0.04)")
finally:
    br.stop()
