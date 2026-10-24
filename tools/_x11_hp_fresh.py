#!/usr/bin/env python3
"""Satu sesi X11 lewat PROXY HP SEGAR (rotate dulu) — kombinasi yang belum diuji:
IP residensial + browser tanpa protokol otomasi.

Uji sebelumnya lewat proxy HP memakai Playwright/CDP (yang memang tidak pernah
memunculkan gate), jadi kegagalannya tidak informatif. Sekarang X11 + IP segar.
"""
import os
import random
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from px_hand import Hand

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11hp2"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11hp2_profile"
URL = "https://signup.live.com/signup?lic=1"
BX, BY = 660, 689


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def log(m):
    print(m, flush=True)


# --- rotate ke IP baru, tunggu egress berubah ---
proxy = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
log("rotate IP HP...")
subprocess.run(["curl", "-s", "--max-time", "40",
                "http://178.83.181.16:18081/rotate?token=capok123"], check=False,
               stdout=subprocess.DEVNULL)
old = run("curl", "-s", "--max-time", "30", "-x", proxy, "https://api.ipify.org")
new = old
for i in range(12):
    time.sleep(6)
    new = run("curl", "-s", "--max-time", "30", "-x", proxy, "https://api.ipify.org")
    log(f"  [{i+1}] egress={new or 'kosong'}")
    if new and new != old:
        break
log(f"IP lama={old} baru={new}")

subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
time.sleep(2.5)
subprocess.run(["rm", "-rf", PROFILE], check=False)
os.makedirs(PROFILE, exist_ok=True)
subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  f"--proxy-server={proxy}",
                  "--fingerprint=424242", "--fingerprint-platform=windows",
                  "--window-size=1280,900", "--window-position=0,0",
                  "--no-first-run", "--no-default-browser-check", URL],
                 stdout=open("/tmp/x11hp2.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})
log("browser lewat proxy HP dijalankan")
time.sleep(18)

best, a0 = None, 0
for w in run("xdotool", "search", "--name", "").splitlines():
    t = run("xdotool", "getwindowname", w)
    if not t or "clipboard" in t.lower():
        continue
    m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
    if m and int(m.group(1)) * int(m.group(2)) > a0:
        best, a0 = w, int(m.group(1)) * int(m.group(2))
WID = best
log(f"WID: {WID} | {run('xdotool', 'getwindowname', WID)}")


def T():
    return run("xdotool", "getwindowname", WID)


def S(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def key(k, w=0.6):
    subprocess.run(["xdotool", "key", "--window", WID, k], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(w)


def typ(s):
    subprocess.run(["xdotool", "type", "--window", WID, "--delay", "55", s], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


hand = Hand(":99")
subprocess.run(["xdotool", "windowactivate", WID], check=False,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
key("ctrl+l", 0.6); typ(URL); key("Return", 11)
log(f"form: {T()}")
S("form")

email = f"x11p{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
log(f"email: {email}")

hand.click(638, 498); typ(email); S("email")
hand.click(638, 574); time.sleep(7); log(f"after email: {T()}")
hand.click(638, 535); typ(pw); S("pw")
hand.click(638, 645); time.sleep(7); log(f"after pw: {T()}")
for label, (dx, dy) in [("month", (516, 536)), ("day", (639, 536))]:
    hand.click(dx, dy); time.sleep(1.1)
    key("Down", 0.35); key("Down", 0.35); key("Return", 1.1)
hand.click(760, 536); typ(str(random.randint(1988, 2000)))
hand.click(640, 710); time.sleep(7); log(f"after birthdate: {T()}")
S("details")
hand.click(650, 432); typ(random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
hand.click(650, 512); typ(random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]))
hand.click(650, 722); time.sleep(12)
t = T()
log(f"after submit: {t}")
S("submit")
if "prove" not in t.lower():
    time.sleep(10); t = T(); log(f"lagi: {t}"); S("wait")

if "prove" not in t.lower():
    log(f">>> TIDAK ada gate: {t}")
    sys.exit(2)

log(">>> GATE MUNCUL (IP HP segar + X11) — press & hold biomekanik")
time.sleep(1.5); S("gate")
held = hand.press_and_hold(seconds=9.0, x=BX, y=BY, log=log)
time.sleep(2.5); S("released"); log(f"setelah lepas: {T()}")
time.sleep(5); log(f"+5s: {T()}")
time.sleep(10); t = T(); log(f"final: {t}"); S("final")
log(">>> LOLOS" if "prove" not in t.lower() else ">>> masih di gate")
