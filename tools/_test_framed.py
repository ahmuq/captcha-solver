#!/usr/bin/env python3
"""Uji hipotesis: halaman challenge PX hanya render bila dibuka DI DALAM iframe.

Observasi: membuka https://iframe.hsprotect.net/index.html?... sebagai navigasi
top-level menghasilkan halaman blank tanpa judul. Halaman challenge memang dirancang
hidup sebagai iframe di dalam halaman host (Microsoft signup), dan banyak challenge
semacam ini menolak render bila `window.top === window.self`.

Uji: sajikan halaman lokal yang MENANAM iframe itu, lalu buka halaman lokal tersebut
di browser tanpa protokol otomasi. Bila gate render -> hipotesis terbukti dan jalur
sessionless jadi: halaman pembungkus lokal + iframe milik caller.
"""
import http.server
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
SID = sys.argv[1] if len(sys.argv) > 1 else "c47b4333737040d896672da5593e77a5"
APP = "PXzC5j78di"
PORT = 8791

PAGE = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Host</title>
<style>html,body{{margin:0;height:100%}}iframe{{width:100%;height:100%;border:0}}</style>
</head><body>
<iframe src="https://iframe.hsprotect.net/index.html?app_id={APP}&session_id={SID}"
        allow="clipboard-write"></iframe>
</body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = socketserver.TCPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
print(f"server lokal di http://127.0.0.1:{PORT}/")

profile = f"/tmp/_framed_{int(time.time())}"
br = Browser(profile, proxy=PROXY)
try:
    br.start(f"http://127.0.0.1:{PORT}/", 22.0)
    wid = br.window_id()
    print(f"title: {br.title(wid)!r}" if wid else "window tidak ketemu")
    shot = f"/tmp/_framed_gate_{int(time.time())}.png"
    if wid and br.screenshot(shot, wid):
        sd = subprocess.run(["convert", shot, "-colorspace", "Gray", "-format",
                             "%[fx:standard_deviation]", "info:"],
                            capture_output=True, text=True).stdout.strip()
        print(f"screenshot: {shot}")
        print(f"std-dev: {sd}  (blank ~0.04, ada konten > 0.10)")
finally:
    br.stop()
    srv.shutdown()
