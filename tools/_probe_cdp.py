#!/usr/bin/env python3
"""Probe langsung: apakah CDP CloakBrowser bisa naik pada profil baru saat ini?"""
import json
import os
import subprocess
import time
import urllib.request

os.environ["DISPLAY"] = ":99"
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = f"/tmp/_probe_{int(time.time())}"
PORT = 9377

args = [BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
        f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1280,900", "--window-position=0,0",
        "https://iframe.hsprotect.net/index.html"]
print("launch:", " ".join(args[:4]), "...")
proc = subprocess.Popen(args, stdout=open("/tmp/_probe.log", "w"),
                        stderr=subprocess.STDOUT, env={**os.environ, "DISPLAY": ":99"})
print("pid:", proc.pid)

ok = False
t0 = time.time()
while time.time() - t0 < 50:
    time.sleep(2)
    if proc.poll() is not None:
        print(f"browser MATI setelah {time.time()-t0:.0f}s, exit={proc.returncode}")
        break
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version",
                                    timeout=3) as r:
            v = json.load(r)
        print(f"CDP naik setelah {time.time()-t0:.0f}s: {v.get('Browser')}")
        ok = True
        break
    except Exception:
        print(f"  {time.time()-t0:.0f}s: belum...")

print("\n=== log browser ===")
print(open("/tmp/_probe.log").read()[-700:])
subprocess.run(["pkill", "-9", "-f", f"user-data-dir={PROFILE}"], check=False)
subprocess.run(["rm", "-rf", PROFILE], check=False)
print("\nHASIL:", "CDP OK" if ok else "CDP GAGAL")
