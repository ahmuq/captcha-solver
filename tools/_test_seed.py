#!/usr/bin/env python3
"""Uji apakah `vid` caller benar-benar tertanam di profil solver.

Membuktikan dua hal:
  1. cookie `_pxvid` tertimpa lewat CDP Network.setCookie (PX menaruh miliknya sebagai
     httpOnly, jadi `document.cookie` tidak bisa menimpanya);
  2. saat challenge dibuka TANPA protokol otomasi, halaman melihat vid kita —
     dicek lewat `window._pxVid` setelah wrapper mengirim postMessage.
"""
import os
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser          # noqa: E402
from perimeterx.seed import seed_visitor        # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
VID = sys.argv[1] if len(sys.argv) > 1 else "33787df6-c977-11f1-b097-31232c7aa85c"
PROFILE = f"/tmp/_seedtest_{int(time.time())}"

print(f"vid yang akan ditanam : {VID}")
print(f"profil                : {PROFILE}")

rep = seed_visitor(PROFILE, APP, VID, PROXY)
print("\n=== hasil seeding ===")
for k in ("seeded", "cookie", "localstorage", "cookie_visible_to_js", "error"):
    print(f"  {k:22}: {rep.get(k)}")
print(f"  user_agent            : {(rep.get('user_agent') or '')[:60]}")

if not rep.get("seeded"):
    print("\nSEEDING GAGAL — perbaiki dulu sebelum lanjut")
    sys.exit(1)

# Buka challenge lewat wrapper (butuh parent postMessage) lalu baca window._pxVid.
# Pembacaan DOM butuh CDP, jadi: buka dengan CDP dulu untuk verifikasi nilai.
import json
import subprocess
import urllib.request

PORT = 9361
args = [__import__("perimeterx.x11", fromlist=["browser_binary"]).browser_binary(),
        f"--user-data-dir={PROFILE}", "--no-sandbox", f"--proxy-server={PROXY}",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=0,0",
        "https://iframe.hsprotect.net/index.html"]
proc = subprocess.Popen(args, stdout=open("/tmp/_seedtest.log", "w"),
                        stderr=subprocess.STDOUT,
                        env={**os.environ, "DISPLAY": ":99"})
try:
    t0, pages = time.time(), []
    while time.time() - t0 < 30:
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list",
                                        timeout=3) as r:
                pages = [t for t in json.load(r) if t.get("type") == "page"]
            if pages:
                break
        except Exception:
            continue
    time.sleep(8)

    from websockets.sync.client import connect
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
        expr = ("JSON.stringify({"
                "pxVid: window._pxVid || null,"
                "ck: document.cookie.indexOf('_pxvid=') >= 0,"
                "ls: localStorage.getItem('" + APP + "_pxvid')})")
        sock.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                              "params": {"expression": expr, "returnByValue": True}}))
        while True:
            m = json.loads(sock.recv())
            if m.get("id") == 1:
                print("\n=== di dalam halaman challenge ===")
                print(" ", ((m.get("result") or {}).get("result") or {}).get("value"))
                break
finally:
    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
    subprocess.run(["rm", "-rf", PROFILE], check=False)
