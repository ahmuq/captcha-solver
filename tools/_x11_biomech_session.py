#!/usr/bin/env python3
"""Sesi Outlook penuh dengan TANGAN BIOMEKANIK (XTest 100 Hz) -> press & hold PX.

Alur: launch tanpa protokol otomasi -> walk signup (klik + ketik) -> gate PX ->
press_and_hold dengan tremor/drift nyata -> lapor hasil + panen _px3.
"""
import os
import random
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from px_hand import Hand

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11hand"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11hand_profile"
URL = "https://signup.live.com/signup?lic=1"
BX, BY = 660, 689


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def log(msg):
    print(msg, flush=True)


# ---------- launch tanpa protokol otomasi ----------
subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
time.sleep(2)
subprocess.run(["rm", "-rf", PROFILE], check=False)
os.makedirs(PROFILE, exist_ok=True)
subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  "--fingerprint=424242", "--fingerprint-platform=windows",
                  "--window-size=1280,900", "--window-position=0,0",
                  "--no-first-run", "--no-default-browser-check", URL],
                 stdout=open("/tmp/x11hand.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})
log("browser dijalankan (tanpa --remote-debugging-*)")
time.sleep(17)


def find_wid():
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best


WID = find_wid()
log(f"WID: {WID} | {run('xdotool', 'getwindowname', WID)}")


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def key(k, wait=0.6):
    subprocess.run(["xdotool", "key", "--window", WID, k], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)


def typ(s):
    subprocess.run(["xdotool", "type", "--window", WID, "--delay", "55", s],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


hand = Hand(":99")
subprocess.run(["xdotool", "windowactivate", WID], check=False,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)

# ---------- buka form ----------
key("ctrl+l", 0.6)
typ(URL)
key("Return", 11)
log(f"form: {title()}")
shot("H0_form")

email = f"x11h{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
log(f"email: {email}")

# step 1: email
hand.click(638, 498)
typ(email)
shot("H1_email")
hand.click(638, 574)
time.sleep(7)
log(f"after email: {title()}")
shot("H2_pw")

# step 2: password
hand.click(638, 535)
typ(pw)
shot("H3_pw")
hand.click(638, 645)
time.sleep(7)
log(f"after pw: {title()}")
shot("H4_details")

# step 3: birthdate (dropdown Fluent: klik -> Down -> Enter)
for label, (dx, dy) in [("month", (516, 536)), ("day", (639, 536))]:
    hand.click(dx, dy)
    time.sleep(1.1)
    key("Down", 0.35)
    key("Down", 0.35)
    key("Return", 1.1)
    log(f"  {label} ok")
hand.click(760, 536)
typ(str(random.randint(1988, 2000)))
shot("H5_birthdate")
hand.click(640, 710)
time.sleep(7)
log(f"after birthdate: {title()}")
shot("H6_name")

# step 4: nama
hand.click(650, 432)
typ(random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
hand.click(650, 512)
typ(random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]))
shot("H7_name")
hand.click(650, 722)
time.sleep(12)
t = title()
log(f"after submit: {t}")
shot("H8_submit")
if "prove" not in t.lower():
    time.sleep(10)
    t = title()
    log(f"lagi: {t}")
    shot("H9_wait")
if "prove" not in t.lower():
    log(f">>> gate TIDAK muncul: {t}")
    sys.exit(2)

# ---------- gate PX: tekan & tahan dengan tangan biomekanik ----------
log(">>> GATE MUNCUL — press & hold dengan tangan biomekanik")
time.sleep(1.5)
shot("H10_gate")
held = hand.press_and_hold(seconds=9.0, x=BX, y=BY, log=log)
log(f"  tahan {held:.1f}s selesai")
time.sleep(2.5)
shot("H11_released")
log(f"setelah lepas: {title()}")
time.sleep(5)
shot("H12_after5")
log(f"+5s: {title()}")
time.sleep(10)
shot("H13_final")
t = title()
log(f"final: {t}")

# ---------- panen cookie ----------
try:
    cp = f"/tmp/_hand_ck.db"
    subprocess.run(["cp", f"{PROFILE}/Default/Cookies", cp], check=True)
    c = sqlite3.connect(cp)
    rows = c.execute("select name,host_key,length(encrypted_value) "
                     "from cookies").fetchall()
    px = [r for r in rows if r[0].startswith("_px") or r[0] == "pxcts"]
    log(f"cookie PX: {[(n, l) for n, h, l in px]}")
    if "prove" not in t.lower():
        log(">>> LOLOS — halaman maju dari gate!")
    else:
        log(">>> masih di gate (ditolak atau belum selesai)")
except Exception as e:
    log(f"gagal baca cookie: {e}")
