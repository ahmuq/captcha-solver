#!/usr/bin/env python3
"""Press-and-hold dengan xdotool TANPA --sync.

BUG sebelumnya: `xdotool mousemove --sync` memblokir ~15 detik pada halaman gate ini
(diukur: 0.00s lalu 15.21s, 15.21s), jadi "hold" yang terjadi sebenarnya cuma
mousedown -> pointer macet 15s -> mouseup, tanpa gerakan sama sekali. Tanpa --sync
panggilan mousemove selesai dalam 0.01s, jadi gesture-nya benar-benar terbentuk.
"""
import os
import random
import subprocess
import time

DISPLAY = ":99"
WID = os.environ.get("WID", "2097155")
BX = int(os.environ.get("BX", "660"))
BY = int(os.environ.get("BY", "689"))
HOLD = float(os.environ.get("HOLD", "8"))
os.environ["DISPLAY"] = DISPLAY


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return subprocess.run(["xdotool", "getwindowname", WID],
                          capture_output=True, text=True).stdout.strip()


def shot(n):
    subprocess.run(["import", "-window", WID, f"/tmp/x11shots/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    print("judul awal:", title())
    xdo("windowactivate", WID)
    time.sleep(0.5)
    xdo("mousemove", str(BX), str(BY))     # TANPA --sync
    time.sleep(0.9)
    xdo("mousedown", "1")
    print(f"  mousedown @ {BX},{BY}, tahan {HOLD}s")

    t0 = time.time()
    cx, cy = float(BX), float(BY)
    it = 0
    while time.time() - t0 < HOLD:
        # tremor natural: amplitudo kecil, interval tidak seragam
        cx = min(max(cx + random.uniform(-1.4, 1.4), BX - 20), BX + 20)
        cy = min(max(cy + random.uniform(-1.0, 1.0), BY - 6), BY + 6)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.05, 0.18))
    print(f"  iterasi gerak: {it} (elapsed {time.time()-t0:.1f}s)")
    shot("70_holding")
    xdo("mouseup", "1")
    print("  mouseup")
    time.sleep(3)
    shot("71_released")
    print("judul setelah lepas:", title())
    time.sleep(10)
    shot("72_settled")
    print("judul akhir:", title())


if __name__ == "__main__":
    main()
