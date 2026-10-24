#!/usr/bin/env python3
"""Buka ulang form signup, lalu verifikasi tiap langkah dengan screenshot.

Pelajaran: window target harus dicari ulang tiap saat (bisa ada tab lain), dan
verifikasi judul setelah SETIAP aksi supaya tidak lanjut di halaman yang salah.
"""
import os
import random
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11shots"
URL = "https://signup.live.com/signup?lic=1"


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def find_wid():
    """Window chrome yang judulnya halaman Microsoft (bukan support)."""
    for pat in ["Microsoft account", "Add some details", "Add your name",
                "prove you're human", "Chromium"]:
        out = run("xdotool", "search", "--name", pat)
        for w in out.splitlines():
            t = run("xdotool", "getwindowname", w)
            if "Microsoft Support" in t:
                continue
            return w
    return None


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


WID = find_wid()
if not WID:
    print("window tidak ketemu"); sys.exit(1)
print("window:", WID, "|", run("xdotool", "getwindowname", WID))

xdo("windowactivate", WID); time.sleep(0.6)

# buka URL form di tab yang ada
xdo("key", "ctrl+l"); time.sleep(0.5)
xdo("type", "--delay", "30", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(10)
print("setelah buka URL:", run("xdotool", "getwindowname", WID))
shot("R0_form")

email = f"x11w{random.randint(100000,999999)}@outlook.com"
print("email:", email)
type_here(638, 498, email)
shot("R1_email")
click_at(638, 574)
time.sleep(7)
t = run("xdotool", "getwindowname", WID)
print("setelah Next email:", t)
shot("R2_after_email")
