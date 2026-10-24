#!/usr/bin/env python3
"""Uji hipotesis FINAL: challenge PX hanya render bila parent mengirim postMessage.

Bukti dari skrip inline halaman challenge (dibaca via CDP):

    window.addEventListener("message", ... switch(o){
        case "block": d(e.jsonResponse, e.requestUrl); break;   // <- kunci
        case "setToWindow": p(e.key, e.value); break; ...})
    function d(t,n){ window._pxUuid=t.uuid; window._pxVid=t.vid; i("captcha") }
    captcha: `${appId}/captcha.js?a=c&m=0&u=${window._pxUuid}&v=${window._pxVid}`

captcha.js — yang merender press-and-hold — dimuat HANYA setelah parent mengirim
pesan "block" berisi uuid+vid. Microsoft adalah parent itu; solver membuka iframe
tanpa parent sehingga #px-captcha kosong dan halaman blank (terukur: hasCaptcha=true,
captchaHTML="", _pxVid undefined).

Uji: halaman pembungkus lokal menanam iframe challenge lalu mengirim pesan "block"
dengan uuid/vid milik caller. Bila gate render -> jalur produksi terbukti.
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"
from perimeterx.browser import Browser   # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
SID = sys.argv[1] if len(sys.argv) > 1 else "19959f4e-2c40-4352-a12c-fc03dff57cce"
UUID = sys.argv[2] if len(sys.argv) > 2 else "33787da7-c977-11f1-b097-3077440506df"
VID = sys.argv[3] if len(sys.argv) > 3 else "33787df6-c977-11f1-b097-31232c7aa85c"
PORT = 8797

CHALLENGE = (f"https://iframe.hsprotect.net/index.html"
             f"?app_id={APP}&session_id={SID}")

tpl = open(os.path.join(os.path.dirname(__file__), "px_host.html")).read()
PAGE = (tpl.replace("__CHALLENGE__", CHALLENGE)
           .replace("__UUID__", json.dumps(UUID))
           .replace("__VID__", json.dumps(VID)))

EVENTS = []


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._send(PAGE)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8", "replace")
        try:
            EVENTS.append(json.loads(raw))
        except Exception:
            EVENTS.append({"raw": raw[:400]})
        self._send("ok", "text/plain")

    def log_message(self, *a):
        pass


srv = socketserver.ThreadingTCPServer(("127.0.0.1", PORT), H)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"server: http://127.0.0.1:{PORT}/")
print(f"challenge: {CHALLENGE}")
print(f"uuid={UUID} vid={VID}")

profile = f"/tmp/_parent2_{int(time.time())}"
br = Browser(profile, proxy=PROXY)
try:
    br.start(f"http://127.0.0.1:{PORT}/", 28.0)
    wid = br.window_id()
    print(f"title: {br.title(wid)!r}" if wid else "window tidak ketemu")
    shot = f"/tmp/_parent2_gate_{int(time.time())}.png"
    if wid and br.screenshot(shot, wid):
        sd = subprocess.run(["convert", shot, "-colorspace", "Gray", "-format",
                             "%[fx:standard_deviation]", "info:"],
                            capture_output=True, text=True).stdout.strip()
        print(f"screenshot: {shot}")
        print(f"std-dev: {sd}  (blank ~0.04, ada konten > 0.10)")

    print(f"\n=== {len(EVENTS)} pesan dari halaman ===")
    for e in EVENTS[:16]:
        print("  ", json.dumps(e)[:230])
    ck = [e for e in EVENTS if isinstance(e.get("data"), dict)
          and e["data"].get("type") == "cookie"]
    if ck:
        print("\n=== COOKIE via postMessage ===")
        for e in ck:
            d = e["data"]
            v = str(d.get("value") or "")
            print(f"   {d.get('name')} len={len(v)} head={v[:40]!r}")
finally:
    br.stop()
    srv.shutdown()
