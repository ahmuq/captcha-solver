#!/usr/bin/env python3
"""Dump skrip inline halaman challenge PX untuk melihat bagaimana _pxUuid/_pxVid diisi."""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"
from perimeterx.browser import browser_binary   # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else (
    "https://iframe.hsprotect.net/index.html?app_id=PXzC5j78di"
    "&session_id=eed812f8-c322-47f6-9968-eaa776284d5a")
PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
PORT = 9351
PROFILE = f"/tmp/_dump_{int(time.time())}"

proc = subprocess.Popen(
    [browser_binary(), f"--user-data-dir={PROFILE}", "--no-sandbox",
     f"--proxy-server={PROXY}", f"--remote-debugging-port={PORT}",
     "--remote-allow-origins=*", "--no-first-run", "--no-default-browser-check",
     "--window-size=1280,900", "--window-position=0,0", URL],
    stdout=open("/tmp/_dump.log", "w"), stderr=subprocess.STDOUT,
    env={**os.environ, "DISPLAY": ":99"})
try:
    t0 = time.time()
    pages = []
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
    time.sleep(15)

    from websockets.sync.client import connect
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as sock:
        sock.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": "document.body.innerHTML", "returnByValue": True}}))
        while True:
            m = json.loads(sock.recv())
            if m.get("id") == 1:
                html = ((m.get("result") or {}).get("result") or {}).get("value") or ""
                break
    print("=== HTML halaman challenge ===")
    print(html)
    print("\n=== nilai global yang relevan ===")
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=80 * 1024 * 1024) as sock:
        sock.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
            "expression": "JSON.stringify({appId:window._pxAppId,uuid:window._pxUuid,"
                          "vid:window._pxVid,host:window._pxHost,"
                          "hasCaptcha:!!document.getElementById('px-captcha'),"
                          "captchaHTML:(document.getElementById('px-captcha')||{}).innerHTML})",
            "returnByValue": True}}))
        while True:
            m = json.loads(sock.recv())
            if m.get("id") == 1:
                print(((m.get("result") or {}).get("result") or {}).get("value"))
                break
finally:
    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
