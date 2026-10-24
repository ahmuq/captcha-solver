#!/usr/bin/env python3
"""Baca DOM + console halaman challenge PX untuk tahu MENGAPA ia blank.

Blank bisa berarti: JS gagal dimuat, JS error, iframe menolak render karena tidak
dijalankan di dalam parent yang sah, atau PX menolak sesinya. Console + DOM akan
membedakan keempatnya.
"""
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
PORT = 9347
PROFILE = f"/tmp/_domdiag_{int(time.time())}"

args = [browser_binary(), f"--user-data-dir={PROFILE}", "--no-sandbox",
        f"--proxy-server={PROXY}",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=0,0", URL]
proc = subprocess.Popen(args, stdout=open("/tmp/_domdiag.log", "w"),
                        stderr=subprocess.STDOUT,
                        env={**os.environ, "DISPLAY": ":99"})
try:
    t0 = time.time()
    while time.time() - t0 < 30:
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list",
                                        timeout=3) as r:
                targets = json.load(r)
            pages = [t for t in targets if t.get("type") == "page"]
            if pages:
                break
        except Exception:
            continue
    time.sleep(18)   # biarkan JS challenge selesai jalan

    from websockets.sync.client import connect
    ws = pages[0]["webSocketDebuggerUrl"]
    counter = {"i": 0}
    with connect(ws, max_size=80 * 1024 * 1024) as sock:

        def call(method, params=None):
            counter["i"] += 1
            cid = counter["i"]
            sock.send(json.dumps({"id": cid, "method": method,
                                  "params": params or {}}))
            while True:
                m = json.loads(sock.recv())
                if m.get("id") == cid:
                    return m

        call("Runtime.enable")
        call("Log.enable")
        time.sleep(3)

        # kuras pesan console/log yang tertunda
        sock.send(json.dumps({"id": 999, "method": "Runtime.evaluate",
                              "params": {"expression":
                                         "JSON.stringify({"
                                         "url:location.href,"
                                         "title:document.title,"
                                         "bodyLen:document.body?document.body.innerHTML.length:-1,"
                                         "body:document.body?document.body.innerHTML.slice(0,600):'',"
                                         "scripts:[...document.scripts].map(s=>s.src||'inline'),"
                                         "iframes:document.querySelectorAll('iframe').length"
                                         "})", "returnByValue": True}}))
        out = None
        logs = []
        deadline = time.time() + 12
        while time.time() < deadline:
            try:
                m = json.loads(sock.recv())
            except Exception:
                break
            if m.get("id") == 999:
                out = m
            if m.get("method") in ("Runtime.consoleAPICalled", "Log.entryAdded",
                                   "Runtime.exceptionThrown"):
                logs.append(m)

    print("=== DOM ===")
    if out:
        val = ((out.get("result") or {}).get("result") or {}).get("value")
        try:
            d = json.loads(val)
            for k in ("url", "title", "bodyLen", "iframes"):
                print(f"  {k}: {d.get(k)}")
            print(f"  scripts: {d.get('scripts')}")
            print(f"  body[:600]: {d.get('body')!r}")
        except Exception:
            print("  raw:", str(val)[:500])
    print(f"\n=== console/log ({len(logs)} pesan) ===")
    for m in logs[:12]:
        meth = m.get("method")
        p = m.get("params") or {}
        if meth == "Runtime.consoleAPICalled":
            txt = " ".join(str(a.get("value", a.get("description", "")))[:200]
                           for a in (p.get("args") or []))
            print(f"  [console.{p.get('type')}] {txt[:250]}")
        elif meth == "Log.entryAdded":
            e = p.get("entry") or {}
            print(f"  [{e.get('level')}] {str(e.get('text'))[:250]}")
        elif meth == "Runtime.exceptionThrown":
            d = (p.get("exceptionDetails") or {})
            print(f"  [exception] {str(d.get('text'))[:120]} "
                  f"{str((d.get('exception') or {}).get('description'))[:200]}")
finally:
    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={PROFILE}"], check=False)
    time.sleep(2)
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
