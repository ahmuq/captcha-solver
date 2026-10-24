#!/usr/bin/env python3
"""Uji hipotesis FINAL: challenge PX hanya render bila _pxvid tersedia.

Bukti dari skrip inline halaman challenge (dibaca via CDP):

    function v(){ var t = u("_pxvid") || x(); t && (window._pxVid = t) }
    function x(){ var t = localStorage.getItem(window._pxAppId + "_pxvid");
                  return t ? JSON.parse(atob(t)).val : null }
    captcha: `${appId}/captcha.js?a=c&m=0&u=${window._pxUuid}&v=${window._pxVid}`

Terukur: window._pxAppId terisi, #px-captcha ADA tapi KOSONG, _pxVid undefined —
karena solver membuka challenge tanpa _pxvid. Akibatnya captcha.js tidak pernah
dimuat dan halaman blank.

Rencana: tulis localStorage `<appId>_pxvid` = base64(JSON({val: vid})) pada origin
iframe.hsprotect.net lewat CDP, tutup bersih, lalu buka challenge TANPA protokol
otomasi. Bila gate render -> hipotesis terbukti.
"""
import base64
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
SID = sys.argv[1] if len(sys.argv) > 1 else "19959f4e-2c40-4352-a12c-fc03dff57cce"
VID = sys.argv[2] if len(sys.argv) > 2 else "33787df6-c977-11f1-b097-31232c7aa85c"
APP = "PXzC5j78di"
PORT = 9355
PROFILE = f"/tmp/_lsvid_{int(time.time())}"
shutil.rmtree(PROFILE, ignore_errors=True)


def wait_pages(port, timeout=30.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list",
                                        timeout=3) as r:
                pages = [t for t in json.load(r) if t.get("type") == "page"]
            if pages:
                return pages
        except Exception:
            continue
    return []


# --- langkah 1: buka origin challenge dengan CDP untuk menulis localStorage ---
proc = subprocess.Popen(
    [browser_binary(), f"--user-data-dir={PROFILE}", "--no-sandbox",
     f"--proxy-server={PROXY}", f"--remote-debugging-port={PORT}",
     "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
     "--window-size=1280,900", "--window-position=0,0",
     "https://iframe.hsprotect.net/index.html"],
    stdout=open("/tmp/_lsvid.log", "w"), stderr=subprocess.STDOUT,
    env={**os.environ, "DISPLAY": ":99"})

pages = wait_pages(PORT)
print(f"halaman CDP: {len(pages)}")
time.sleep(6)

payload = base64.b64encode(json.dumps({"val": VID}).encode()).decode()
print(f"nilai localStorage {APP}_pxvid = {payload}")

from websockets.sync.client import connect   # noqa: E402

with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
    expr = (f"localStorage.setItem('{APP}_pxvid', '{payload}');"
            f"localStorage.getItem('{APP}_pxvid')")
    sock.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                          "params": {"expression": expr, "returnByValue": True}}))
    while True:
        m = json.loads(sock.recv())
        if m.get("id") == 1:
            got = ((m.get("result") or {}).get("result") or {}).get("value")
            print(f"localStorage ditulis, terbaca kembali: {got!r}")
            break

# --- langkah 2: tutup bersih supaya localStorage ter-flush ---
subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
try:
    proc.wait(timeout=15)
except Exception:
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
time.sleep(3)

# --- langkah 3: buka challenge TANPA protokol otomasi ---
url = f"https://iframe.hsprotect.net/index.html?app_id={APP}&session_id={SID}"
br = Browser(PROFILE, proxy=PROXY)
try:
    br.start(url, 22.0)
    wid = br.window_id()
    title = br.title(wid) if wid else ""
    print(f"title: {title!r}")
    shot = f"/tmp/_lsvid_gate_{int(time.time())}.png"
    if wid and br.screenshot(shot, wid):
        sd = subprocess.run(["convert", shot, "-colorspace", "Gray", "-format",
                             "%[fx:standard_deviation]", "info:"],
                            capture_output=True, text=True).stdout.strip()
        print(f"screenshot: {shot}")
        print(f"std-dev: {sd}  (blank ~0.04, ada konten > 0.10)")
finally:
    br.stop()
