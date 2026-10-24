#!/usr/bin/env python3
"""Loop sesi berjeda: rotasi IP HP -> jeda -> X11 walk -> gate -> hold biomekanik."""
import os, random, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from px_hand import Hand

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11lp"; os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11lp_profile"
URL = "https://signup.live.com/signup?lic=1"
BX, BY = 660, 689
GAP = float(os.environ.get("GAP", "240"))
N = int(os.environ.get("N", "3"))
PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def log(m):
    print(m, flush=True)


def rotate():
    subprocess.run(["curl", "-s", "--max-time", "40",
                    "http://178.83.181.16:18081/rotate?token=capok123"],
                   check=False, stdout=subprocess.DEVNULL)
    for _ in range(10):
        time.sleep(6)
        ip = run("curl", "-s", "--max-time", "25", "-x", PROXY, "https://api.ipify.org")
        if ip:
            return ip
    return "?"


def launch():
    subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
    time.sleep(2.5)
    subprocess.run(["rm", "-rf", PROFILE], check=False)
    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                      f"--proxy-server={PROXY}", "--fingerprint=424242",
                      "--fingerprint-platform=windows", "--window-size=1280,900",
                      "--window-position=0,0", "--no-first-run",
                      "--no-default-browser-check", URL],
                     stdout=open("/tmp/x11lp.log", "w"), stderr=subprocess.STDOUT,
                     env={**os.environ, "DISPLAY": ":99"})
    time.sleep(18)
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best
