#!/usr/bin/env python3
"""Uji hipotesis: CDP boleh aktif asal ada wrapper parent.

Asumsi lama: gate tidak render kalau browser punya protokol otomasi. Tapi uji lama itu
memakai Playwright yang JUGA mengendalikan browser lewat CDP, tanpa parent postMessage.
Belum pernah diuji: CDP aktif + wrapper parent + kontrol X11.

Kalau ini bekerja, dua masalah selesai sekaligus:
  1. `_pxvid` bisa ditanam in-memory (setCookie) lalu LANGSUNG dipakai di sesi yang sama
     tanpa perlu persist ke disk (yang terbukti tidak terjadi);
  2. `_px3` bisa dibaca langsung lewat CDP, tanpa harvest terpisah.

Ukuran keberhasilan: window._pxVid == vid yang kita tanam, DAN gate render.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.sessionless import _Wrapper          # noqa: E402
from perimeterx.x11 import browser_binary            # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
VID = sys.argv[1] if len(sys.argv) > 1 else "afb41954-c983-11f1-b109-bcb6b481123f"
UUID = sys.argv[2] if len(sys.argv) > 2 else "afb4190d-c983-11f1-b109-3077440506df"
SID = sys.argv[3] if len(sys.argv) > 3 else "dbac51d5-b5e8-4270-b716-274548026a0a"
PORT = 9385
PROFILE = f"/tmp/_cdpwrap_{int(time.time())}"

challenge = (f"https://iframe.hsprotect.net/index.html"
             f"?app_id={APP}&session_id={SID}")
wrap = _Wrapper(challenge, UUID, VID)
print(f"wrapper: {wrap.url}")
print(f"vid ditanam: {VID}")

args = [browser_binary(), f"--user-data-dir={PROFILE}", "--no-sandbox",
        f"--proxy-server={PROXY}",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=0,0",
        "https://iframe.hsprotect.net/index.html"]
proc = subprocess.Popen(args, stdout=open("/tmp/_cdpwrap.log", "w"),
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
    time.sleep(5)

    from websockets.sync.client import connect
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
        cid = [0]

        def call(method, params):
            cid[0] += 1
            sock.send(json.dumps({"id": cid[0], "method": method, "params": params}))
            while True:
                m = json.loads(sock.recv())
                if m.get("id") == cid[0]:
                    return m

        # 1. Tanam _pxvid di sesi ini (in-memory, langsung dipakai)
        r = call("Network.setCookie", {
            "name": "_pxvid", "value": VID, "domain": ".hsprotect.net", "path": "/",
            "secure": True, "httpOnly": True, "sameSite": "None",
            "expires": time.time() + 3600})
        print(f"setCookie success: {(r.get('result') or {}).get('success')}")

        r = call("Network.getCookies", {"urls": ["https://iframe.hsprotect.net/"]})
        got = {c["name"]: c["value"]
               for c in ((r.get("result") or {}).get("cookies") or [])}
        print(f"_pxvid in-memory: {got.get('_pxvid')!r} (cocok={got.get('_pxvid')==VID})")

        # 2. Navigasi ke WRAPPER (bukan iframe langsung) — parent postMessage diperlukan
        call("Page.enable", {})
        r = call("Page.navigate", {"url": wrap.url})
        print(f"navigasi ke wrapper: {r.get('result') or r.get('error')}")

    # 3. Tunggu wrapper mengirim postMessage -> challenge render
    t0 = time.time()
    while time.time() - t0 < 30:
        if wrap.rendered.is_set():
            break
        time.sleep(1)
    print(f"\ngate render (event 'rendered'): {wrap.rendered.is_set()}")
    print(f"cookie diterima solver     : {sorted(wrap.cookies)}")

    # 4. Apakah halaman challenge melihat vid KITA?
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
        cid[0] += 1
        sock.send(json.dumps({"id": cid[0], "method": "Runtime.evaluate", "params": {
            "expression": "JSON.stringify({top: location.href.slice(0,60)})",
            "returnByValue": True}}))
        while True:
            m = json.loads(sock.recv())
            if m.get("id") == cid[0]:
                print("halaman aktif:", ((m.get("result") or {}).get("result") or {}).get("value"))
                break
finally:
    wrap.close()
    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
    subprocess.run(["rm", "-rf", PROFILE], check=False)
