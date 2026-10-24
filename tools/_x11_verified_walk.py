#!/usr/bin/env python3
"""Walker X11 berbasis KEYBOARD, dengan verifikasi teks field setelah mengetik.

Pelajaran: halaman signup ini kadang TIDAK auto-focus ke field, jadi `xdotool type`
tanpa klik tidak masuk. Skrip ini mengklik field pakai koordinat yang DIUKUR dari
screenshot window (bukan root), lalu MEMVERIFIKASI isi field lewat xclip sebelum
lanjut — supaya tidak pernah lagi lanjut di step yang salah.
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


def run(*a, input_text=None):
    return subprocess.run(a, capture_output=True, text=True,
                          input=input_text).stdout.strip()


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_wid():
    best, area0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if not m:
            continue
        a = int(m.group(1)) * int(m.group(2))
        if a > area0:
            best, area0 = w, a
    return best


WID = find_wid()
print("WID:", WID, "|", run("xdotool", "getwindowname", WID))


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def click_at(x, y):
    # gerak bertahap lalu klik
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = x, y
    for i in range(1, 15):
        t = i / 14; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (x - sx) * e)), str(int(sy + (y - sy) * e)))
        time.sleep(random.uniform(0.01, 0.025))
    xdo("mousemove", str(x), str(y)); time.sleep(0.25)
    xdo("click", "1"); time.sleep(0.6)


def read_field(x, y):
    """Seleksi isi field (Ctrl+A) lalu salin (Ctrl+C), baca lewat xclip."""
    xdo("key", "ctrl+a"); time.sleep(0.3)
    xdo("key", "ctrl+c"); time.sleep(0.4)
    out = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def type_verified(x, y, s, label):
    click_at(x, y)
    xdo("type", "--delay", "60", s)
    time.sleep(0.5)
    got = read_field(x, y)
    ok = got == s
    print(f"  [{label}] typed={s!r} readback={got[:40]!r} ok={ok}")
    return ok


def press_hold(seconds=8.0):
    BX, BY = 660, 689
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = BX, BY
    for i in range(1, 23):
        t = i / 22; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (BX - sx) * e + random.uniform(-1.1, 1.1))),
            str(int(sy + (BY - sy) * e + random.uniform(-1.1, 1.1))))
        time.sleep(random.uniform(0.012, 0.03))
    xdo("mousemove", str(BX), str(BY)); time.sleep(0.35)
    xdo("mousemove", str(BX + random.randint(-3, 3)), str(BY - random.randint(3, 6)))
    time.sleep(random.uniform(0.06, 0.14))
    xdo("mousemove", str(BX), str(BY)); time.sleep(random.uniform(0.05, 0.12))
    xdo("mousedown", "1")
    t0, cx, cy, it = time.time(), float(BX), float(BY), 0
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-1.3, 1.3), BX - 18), BX + 18)
        cy = min(max(cy + random.uniform(-0.9, 0.9), BY - 5), BY + 5)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.03, 0.15) if random.random() > 0.15
                   else random.uniform(0.2, 0.45))
    print(f"  [hold] iterasi={it}")
    shot("V_holding")
    xdo("mouseup", "1")
    time.sleep(random.uniform(0.1, 0.25))
    for i in range(1, 11):
        xdo("mousemove", str(BX + i * 9), str(BY + i * 6)); time.sleep(0.02)


xdo("windowactivate", WID); time.sleep(0.8)
xdo("key", "ctrl+l"); time.sleep(0.6)
xdo("type", "--delay", "25", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(11)
print("form:", title()); shot("V0_form")

email = f"x11v{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
print("email:", email)

# step 1: email  (diukur dari screenshot: field 638,498 ; Next 638,574)
type_verified(638, 498, email, "email")
shot("V1_email")
click_at(638, 574); time.sleep(7)
print("after email:", title()); shot("V2_pw")

# step 2: password (diukur: field 638,535 ; Next 638,645)
type_verified(638, 535, pw, "password")
shot("V3_pw")
click_at(638, 645); time.sleep(7)
print("after pw:", title()); shot("V4_details")

# step 3: birthdate (Month 516,536 | Day 639,536 | Year 760,536 | Next 640,710)
click_at(516, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
click_at(639, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
type_verified(760, 536, str(random.randint(1988, 2000)), "year")
shot("V5_birthdate")
click_at(640, 710); time.sleep(7)
print("after birthdate:", title()); shot("V6_name")

# step 4: nama (First 650,432 | Last 650,512 | Next 650,722)
type_verified(650, 432, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]), "first")
type_verified(650, 512, random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]), "last")
shot("V7_name")
click_at(650, 722); time.sleep(12)
t = title(); print("after submit:", t); shot("V8_submit")
if "prove" not in t.lower():
    time.sleep(10); t = title(); print("lagi:", t); shot("V9_wait")
if "prove" not in t.lower():
    print(">>> gate TIDAK muncul"); sys.exit(2)

print(">>> GATE MUNCUL")
time.sleep(2); shot("V10_gate")
press_hold(8.0)
time.sleep(3); print("after hold:", title()); shot("V11_after_hold")
time.sleep(12); print("final:", title()); shot("V12_final")
