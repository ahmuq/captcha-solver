#!/usr/bin/env python3
"""Walker X11 + press-hold PX, koordinat presisi dari analisis visual.

Perbaikan dari percobaan sebelumnya:
  * tombol Next ada di (638,574) — sebelumnya saya klik (640,710) yang jatuh ke footer.
  * field email di (638,498); step lain punya offset berbeda -> pakai koordinat hasil ukur.
  * `xdotool type --window` dikirim ke window; untuk input web lebih andal fokus dulu
    lewat klik, lalu ketik tanpa --window.
"""
import os
import random
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
WID = os.environ.get("WID", "2097155")
SHOTS = "/tmp/x11shots"


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return subprocess.run(["xdotool", "getwindowname", WID],
                          capture_output=True, text=True).stdout.strip()


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def move_smooth(tx, ty, steps=16):
    out = subprocess.run(["xdotool", "getmouselocation"],
                         capture_output=True, text=True).stdout
    try:
        sx = int(out.split()[0].split(":")[1])
        sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = tx, ty
    for i in range(1, steps + 1):
        t = i / steps
        e = 1 - (1 - t) ** 2.2
        x = sx + (tx - sx) * e + random.uniform(-1.2, 1.2)
        y = sy + (ty - sy) * e + random.uniform(-1.2, 1.2)
        xdo("mousemove", str(int(x)), str(int(y)))
        time.sleep(random.uniform(0.012, 0.03))
    xdo("mousemove", str(tx), str(ty))
    time.sleep(random.uniform(0.12, 0.3))


def click_at(x, y):
    move_smooth(x, y)
    xdo("click", "1")
    time.sleep(0.5)


def type_here(x, y, s):
    click_at(x, y)
    xdo("type", "--delay", "65", s)
    time.sleep(0.4)


def press_hold(bx, by, seconds=8.0):
    print(f"  [hold] approach ({bx},{by})")
    move_smooth(bx, by, steps=20)
    xdo("mousemove", str(bx + random.randint(-3, 3)), str(by - random.randint(3, 6)))
    time.sleep(random.uniform(0.06, 0.14))
    xdo("mousemove", str(bx), str(by))
    time.sleep(random.uniform(0.04, 0.10))
    xdo("mousedown", "1")
    print(f"  [hold] tahan {seconds}s")
    t0, cx, cy, it = time.time(), float(bx), float(by), 0
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-1.3, 1.3), bx - 18), bx + 18)
        cy = min(max(cy + random.uniform(-0.9, 0.9), by - 5), by + 5)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.03, 0.15) if random.random() > 0.15
                   else random.uniform(0.2, 0.45))
    print(f"  [hold] iterasi={it}")
    shot("P1_holding")
    xdo("mouseup", "1")
    time.sleep(random.uniform(0.1, 0.25))
    move_smooth(bx + random.randint(60, 110), by + random.randint(40, 80), steps=10)


def main():
    print("judul:", title())
    xdo("windowactivate", WID)
    time.sleep(0.8)
    email = f"x11w{random.randint(100000,999999)}@outlook.com"
    pw = "Zx9kLmQ2vRt7pW!4"
    print("email:", email)

    # step 1: email  (field 638,498 | Next 638,574)
    type_here(638, 498, email)
    shot("Q1_email_typed")
    click_at(638, 574)
    time.sleep(6)
    print("after email:", title())
    shot("Q2_pw")

    # step 2: password (cari posisi via asumsi layout sama: field ~638,498; Next ~638,574)
    type_here(638, 498, pw)
    shot("Q3_pw_typed")
    click_at(638, 574)
    time.sleep(6)
    print("after pw:", title())
    shot("Q4_details")

    return 0


if __name__ == "__main__":
    sys.exit(main())
