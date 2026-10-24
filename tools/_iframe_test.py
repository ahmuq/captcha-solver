#!/usr/bin/env python3
"""Uji kunci: bisakah challenge iframe PX dibuka LANGSUNG tanpa alur signup?

Kalau ya, solver tidak perlu renderer register sama sekali: cukup buka
  https://iframe.hsprotect.net/index.html?app_id=<APPID>&session_id=<UAID>
lalu kerjakan press & hold dan panen _px3 — persis kontrak Offcaptcha
(PXCaptchaSessionlessPressAndHold) yang menerima sessionId/uuid/vid dari caller.

Uji ini memakai session_id sembarang dulu, hanya untuk melihat apakah gate
benar-benar dirender di iframe (bukan apakah tokennya diterima Microsoft).
"""
import os
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11iframe"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11iframe_profile"
APPID = os.environ.get("APPID", "PXzC5j78di")
SID = os.environ.get("SID", "3f2a9c1e-7b4d-4e21-9a8c-5d6e7f8a9b0c")
URL = f"https://iframe.hsprotect.net/index.html?app_id={APPID}&session_id={SID}"


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
time.sleep(2)
subprocess.run(["rm", "-rf", PROFILE], check=False)
os.makedirs(PROFILE, exist_ok=True)
subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  "--fingerprint=424242", "--fingerprint-platform=windows",
                  "--window-size=1280,900", "--window-position=0,0",
                  "--no-first-run", "--no-default-browser-check", URL],
                 stdout=open("/tmp/x11iframe.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})
print(f"buka: {URL}")
time.sleep(20)

best, a0 = None, 0
for w in run("xdotool", "search", "--name", "").splitlines():
    t = run("xdotool", "getwindowname", w)
    if not t or "clipboard" in t.lower():
        continue
    m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
    if m and int(m.group(1)) * int(m.group(2)) > a0:
        best, a0 = w, int(m.group(1)) * int(m.group(2))
WID = best
print("WID:", WID, "| judul:", run("xdotool", "getwindowname", WID))
subprocess.run(["import", "-window", WID, f"{SHOTS}/iframe.png"], check=False,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("screenshot: /tmp/x11iframe/iframe.png")

# cookie PX apa pun yang terbit di iframe
try:
    import shutil, sqlite3
    shutil.copy2(f"{PROFILE}/Default/Cookies", "/tmp/_if_ck.db")
    con = sqlite3.connect("/tmp/_if_ck.db")
    rows = con.execute("select name,host_key,length(encrypted_value) from cookies").fetchall()
    print("cookie:", rows if rows else "kosong")
except Exception as e:
    print("cookie err:", e)
