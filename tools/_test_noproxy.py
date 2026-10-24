#!/usr/bin/env python3
"""Uji pemisah: jalankan sesi X11 TANPA proxy (IP VPS) sekarang.

Tujuan: kalau gate muncul lagi di VPS, berarti blokir menempel pada proxy HP
(bukan pada flow/akun). Kalau VPS juga diblokir, blokirnya level flow/global.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from _hloop_walk import walk, hold

os.environ["DISPLAY"] = ":99"
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11novpn"
URL = "https://signup.live.com/signup?lic=1"


def launch_noproxy():
    import re, subprocess
    subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
    time.sleep(2.5)
    subprocess.run(["rm", "-rf", PROFILE], check=False)
    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                      "--fingerprint=424242", "--fingerprint-platform=windows",
                      "--window-size=1280,900", "--window-position=0,0",
                      "--no-first-run", "--no-default-browser-check", URL],
                     stdout=open("/tmp/x11novpn.log", "w"), stderr=subprocess.STDOUT,
                     env={**os.environ, "DISPLAY": ":99"})
    time.sleep(18)
    best, a0 = None, 0
    for w in _hloop.run("xdotool", "search", "--name", "").splitlines():
        t = _hloop.run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)",
                      _hloop.run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best


WID = launch_noproxy()
_hloop.log(f"WID: {WID} | {_hloop.run('xdotool', 'getwindowname', WID)}")
t = walk(WID, "novpn")
_hloop.log(f"hasil submit: {t}")
if "prove" in t.lower():
    t = hold(WID, "novpn")
    _hloop.log(">>> LOLOS" if "prove" not in t.lower() else ">>> masih di gate")
else:
    _hloop.log(">>> TIDAK ada gate di IP VPS")
