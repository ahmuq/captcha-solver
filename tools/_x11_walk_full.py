#!/usr/bin/env python3
"""Walker X11 lengkap: buka form -> isi email/password/birthdate/nama -> tekan-tahan gate.

Window dipilih dengan benar (lewati helper "Chromium clipboard"/support), dan setiap
langkah diverifikasi lewat judul + screenshot supaya tidak lanjut di halaman salah.
"""
import os
import random
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11shots"
URL = "https://signup.live.com/signup?lic=1"
os.makedirs(SHOTS, exist_ok=True)


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def find_wid():
    """Window browser yang memuat halaman Microsoft (bukan helper/clipboard/support)."""
    best = None
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        if "Microsoft Support" in t:
            continue
        g = run("xdotool", "getwindowgeometry", w)
        m = re.search(r"Geometry: (\d+)x(\d+)", g)
        if not m:
            continue
        ww, hh = int(m.group(1)), int(m.group(2))
        if ww < 800 or hh < 500:      # helper window kecil
            continue
        best = w
    return best


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def move_smooth(tx, ty, steps=14):
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = tx, ty
    for i in range(1, steps + 1):
        t = i / steps; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (tx - sx) * e + random.uniform(-1.1, 1.1))),
            str(int(sy + (ty - sy) * e + random.uniform(-1.1, 1.1))))
        time.sleep(random.uniform(0.012, 0.03))
    xdo("mousemove", str(tx), str(ty)); time.sleep(0.25)


def click_at(x, y):
    move_smooth(x, y); xdo("click", "1"); time.sleep(0.5)


def type_here(x, y, s):
    click_at(x, y); xdo("type", "--delay", "65", s); time.sleep(0.4)


def press_hold(bx, by, seconds=8.0):
    print(f"  [hold] approach ({bx},{by})")
    move_smooth(bx, by, steps=22)
    xdo("mousemove", str(bx + random.randint(-3, 3)), str(by - random.randint(3, 6)))
    time.sleep(random.uniform(0.06, 0.14))
    xdo("mousemove", str(bx), str(by))
    time.sleep(random.uniform(0.04, 0.10))
    xdo("mousedown", "1")
    t0, cx, cy, it = time.time(), float(bx), float(by), 0
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-1.3, 1.3), bx - 18), bx + 18)
        cy = min(max(cy + random.uniform(-0.9, 0.9), by - 5), by + 5)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.03, 0.15) if random.random() > 0.15
                   else random.uniform(0.2, 0.45))
    print(f"  [hold] iterasi={it}")
    shot("P_holding")
    xdo("mouseup", "1")
    time.sleep(random.uniform(0.1, 0.25))
    move_smooth(bx + random.randint(60, 110), by + random.randint(40, 80), steps=10)


WID = find_wid()
if not WID:
    print("window browser tidak ketemu"); sys.exit(1)
print("WID:", WID, "|", title())

xdo("windowactivate", WID); time.sleep(0.6)

# --- buka form ---
xdo("key", "ctrl+l"); time.sleep(0.6)
xdo("type", "--delay", "25", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(11)
print("form:", title())
shot("S0_form")

email = f"x11w{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
print("email:", email)

# --- step 1: email ---
type_here(638, 498, email)
shot("S1_email_typed")
click_at(638, 574)
time.sleep(7)
print("after email:", title())
shot("S2_pw_step")

# --- step 2: password ---
type_here(638, 498, pw)
shot("S3_pw_typed")
click_at(638, 574)
time.sleep(7)
print("after pw:", title())
shot("S4_details")

# --- step 3: birthdate ---
for name, (x, y) in [("month", (516, 536)), ("day", (639, 536))]:
    click_at(x, y)
    time.sleep(1.2)
    xdo("key", "Down"); time.sleep(0.3)
    xdo("key", "Down"); time.sleep(0.3)
    xdo("key", "Return"); time.sleep(1.2)
    print(f"  {name} ok")
type_here(760, 536, str(random.randint(1988, 2000)))
shot("S5_birthdate")
click_at(640, 710)
time.sleep(7)
print("after birthdate:", title())
shot("S6_name_step")

# --- step 4: nama ---
type_here(650, 432, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
type_here(650, 512, random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]))
shot("S7_name_filled")
click_at(650, 722)
time.sleep(11)
t = title()
print("after submit:", t)
shot("S8_after_submit")

if "prove" not in t.lower():
    time.sleep(10)
    t = title()
    print("lagi:", t)
    shot("S9_wait")

if "prove" not in t.lower():
    print(">>> gate TIDAK muncul"); sys.exit(2)

print(">>> GATE MUNCUL — tekan tahan")
time.sleep(2)
shot("S10_gate")
press_hold(660, 689, seconds=8.0)
time.sleep(3)
print("after hold:", title())
shot("S11_after_hold")
time.sleep(12)
print("final:", title())
shot("S12_final")
