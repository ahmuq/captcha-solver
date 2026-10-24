#!/usr/bin/env python3
"""Uji hipotesis FINAL: challenge PX hanya render bila parent mengirim postMessage.

Bukti dari skrip inline halaman challenge (dibaca via CDP):

    window.addEventListener("message", function(n){ ... switch(o){
        case "block":       d(e.jsonResponse, e.requestUrl); break;   // <- kunci
        case "setToWindow": p(e.key, e.value); break;
        case "focus":       a() }})

    function d(t,n){ window._pxUuid = t.uuid; window._pxVid = t.vid;
                     window._pxBlockedUrl = n; i("captcha") }   // i() memuat captcha.js
    captcha: `${appId}/captcha.js?a=c&m=0&u=${window._pxUuid}&v=${window._pxVid}`

Jadi captcha.js — yang merender press-and-hold — dimuat HANYA setelah parent mengirim
pesan "block" berisi uuid+vid. Microsoft adalah parent itu; solver kita membuka iframe
tanpa parent, sehingga #px-captcha tetap kosong dan halaman blank (terukur).

Uji: halaman pembungkus lokal menanam iframe challenge lalu mengirim pesan "block"
dengan uuid/vid milik caller. Bila gate render -> jalur produksi terbukti.

Bonus: halaman challenge mengirim balik cookie lewat postMessage
    window.parent.postMessage({type:"cookie",name:t,value:n,expires:e},"*")
jadi _px3 bisa dipanen langsung tanpa relaunch CDP.
"""
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"
from perimeterx.browser import Browser   # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
SID = sys.argv[1] if len(sys.argv) > 1 else "19959f4e-2c40-4352-a12c-fc03dff57cce"
UUID = sys.argv[2] if len(sys.argv) > 2 else "33787da7-c977-11f1-b097-3077440506df"
VID = sys.argv[3] if len(sys.argv) > 3 else "33787df6-c977-11f1-b097-31232c7aa85c"
PORT = 8795

CHALLENGE = (f"https://iframe.hsprotect.net/index.html"
             f"?app_id={APP}&session_id={SID}")

PAGE = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>PX Host</title>
<style>html,body{{margin:0;height:100%;background:#fff}}
iframe{{width:100%;height:100%;border:0}}</style></head><body>
<iframe id="ch" src="{CHALLENGE}"></iframe>
<script>
const f = document.getElementById('ch');
const report = (o) => fetch('/ev', {{method:'POST', body: JSON.stringify(o)}});
window.addEventListener('message', (e) => {{
  report({{kind:'msg', data: e.data}});
}});
// Parent asli (Microsoft) mengirim "block" berisi uuid+vid. Itu yang memicu
// pemuatan captcha.js di dalam iframe.
f.addEventListener('load', () => {{
  report({{kind:'iframe-loaded'}});
  setTimeout(() => {{
    const msg = {{type:'block',
                  jsonResponse: {{vid: {json.dumps(VID)}, uuid: {json.dumps(UUID)}}},
                  requestUrl: 'https://signup.live.com/api/v1.0/risk/verify'}};
    report({{kind:'sending-block', data: msg}});
    f.contentWindow.postMessage(msg, '*');
    setTimeout(() => f.contentWindow.postMessage(
        {{type:'setToWindow', key:'_pxVid', value:{json.dumps(VID)}}}, '*'), 1200);
    setTimeout(() => f.contentWindow.postMessage(
        {{type:'setToWindow', key:'_pxUuid', value:{json.dumps(UUID)}}}, 1400);
  }}, 2500);
}});
</script></body></html>"""

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

profile = f"/tmp/_parent_{int(time.time())}"
br = Browser(profile, proxy=PROXY)
try:
    br.start(f"http://127.0.0.1:{PORT}/", 26.0)
    wid = br.window_id()
    print(f"title: {br.title(wid)!r}" if wid else "window tidak ketemu")
    shot = f"/tmp/_parent_gate_{int(time.time())}.png"
    if wid and br.screenshot(shot, wid):
        sd = subprocess.run(["convert", shot, "-colorspace", "Gray", "-format",
                             "%[fx:standard_deviation]", "info:"],
                            capture_output=True, text=True).stdout.strip()
        print(f"screenshot: {shot}")
        print(f"std-dev: {sd}  (blank ~0.04, ada konten > 0.10)")

    print(f"\n=== {len(EVENTS)} pesan dari halaman ===")
    for e in EVENTS[:14]:
        s = json.dumps(e)
        print("  ", s[:220])
    ck = [e for e in EVENTS if isinstance(e.get("data"), dict)
          and e["data"].get("type") == "cookie"]
    if ck:
        print("\n=== COOKIE dari postMessage ===")
        for e in ck:
            d = e["data"]
            print(f"   {d.get('name')} = {str(d.get('value'))[:50]}... "
                  f"(len={len(str(d.get('value') or ''))})")
finally:
    br.stop()
    srv.shutdown()
