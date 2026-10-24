#!/usr/bin/env python3
"""Panen cookie dari profil yang SUDAH selesai: relaunch profil yang sama dengan CDP.

Ide: tell protokol otomasi hanya menghalangi *render* challenge PX. Setelah gate
selesai di jalur X11, cookie tersimpan di profil; membuka ulang profil yang sama
dengan `--remote-debugging-port` membuat browser sendiri yang mendekripsi store-nya,
jadi kita tidak perlu tahu kunci os_crypt-nya. Diuji pada profil yang sudah punya
_px3 di disk.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh_profile"
PROFILE = "/tmp/_cdp_read_profile"
PORT = 9333
os.environ["DISPLAY"] = ":99"


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


# salin profil supaya profil asli tidak terkunci / berubah
sh("pkill", "-f", f"user-data-dir={PROFILE}")
time.sleep(1)
shutil.rmtree(PROFILE, ignore_errors=True)
shutil.copytree(SRC, PROFILE, symlinks=True)
print(f"profil disalin dari {SRC}")

subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  f"--remote-debugging-port={PORT}",
                  "--remote-allow-origins=*",
                  "--no-first-run", "--no-default-browser-check",
                  "--window-size=900,600", "--window-position=0,0", "about:blank"],
                 stdout=open("/tmp/_cdp_read.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})

ver = None
for _ in range(30):
    time.sleep(1)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=3) as r:
            ver = json.load(r)
            break
    except Exception:
        continue
if not ver:
    print("CDP tidak siap")
    sys.exit(1)
print("CDP siap:", ver.get("Browser"))

# ambil daftar target dan pilih satu page
with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=5) as r:
    targets = json.load(r)
pages = [t for t in targets if t.get("type") == "page"]
if not pages:
    print("tidak ada target page")
    sys.exit(1)
ws = pages[0]["webSocketDebuggerUrl"]
print("target:", pages[0].get("url"))

try:
    from websockets.sync.client import connect
except Exception:
    print("butuh paket websockets")
    sys.exit(1)

out = {}
with connect(ws, max_size=50 * 1024 * 1024) as sock:
    def cmd(mid, method, params=None):
        sock.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(sock.recv())
            if msg.get("id") == mid:
                return msg

    r = cmd(1, "Storage.getCookies")
    cookies = (r.get("result") or {}).get("cookies", [])
    print(f"total cookie via CDP: {len(cookies)}")
    for c in cookies:
        if "hsprotect" in c.get("domain", "") or c["name"] in ("_px3", "_pxvid", "_pxde", "pxcts"):
            out[c["name"]] = c["value"]
            print(f"  {c['name']:8} len={len(c['value']):4} head={c['value'][:20]!r}")

if out:
    json.dump(out, open("/tmp/px_cookies.json", "w"), indent=1)
    print(f">>> {len(out)} cookie PX dipanen -> /tmp/px_cookies.json")
else:
    print("tidak ada cookie PX di profil ini")

sh("pkill", "-f", f"user-data-dir={PROFILE}")
