#!/usr/bin/env python3
"""Uji endpoint /solve mode sessionless lewat proxy HP.

Memanggil solver persis seperti bot Go akan memanggilnya, dan melaporkan seluruh
field respons supaya kelihatan bagian mana yang berhasil/gagal.
"""
import json
import subprocess
import sys
import time
import urllib.request

TOKEN = subprocess.run(
    ["grep", "-oP", r"(?<=SOLVER_API_TOKEN=).*", "/root/captcha-solver/.solver-token.env"],
    capture_output=True, text=True).stdout.strip().strip('"')
PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
URL = "http://127.0.0.1:8877/solve"

payload = {
    "type": "perimeterx",
    "mode": "sessionless",
    "session_id": sys.argv[1] if len(sys.argv) > 1 else "3f2a9c1e-7b4d-4e21-9a8c-5d6e7f8a9b0c",
    "uuid": "test-uuid",
    "vid": "test-vid",
    "app_id": "PXzC5j78di",
    "proxy": PROXY,
    "timeout_s": 180,
}
print("POST /solve sessionless")
print("  session_id:", payload["session_id"][:20])
t0 = time.time()
req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                             headers={"Authorization": "Bearer " + TOKEN,
                                      "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=400) as r:
        body = json.load(r)
except Exception as e:
    print("HTTP error:", e)
    try:
        print("body:", e.read().decode()[:400])
    except Exception:
        pass
    sys.exit(1)

print(f"selesai dalam {time.time()-t0:.0f}s")
for k in ("solved", "gate_reached", "press_hold_actuated", "px3_rotated",
          "elapsed", "error", "note"):
    if k in body:
        print(f"  {k}: {body[k]!r}")
c = body.get("cookies") or {}
print(f"  cookies: {sorted(c)}")
for n in sorted(c):
    print(f"    {n:8} len={len(c[n])}")
if body.get("px3"):
    print(f"  px3 head: {body['px3'][:40]!r}")
