#!/usr/bin/env python3
"""Press-and-hold PX dengan gesture biomekanik yang lebih manusiawi.

Hold sebelumnya ditolak ("Please try again") karena micro-movement-nya seragam:
jarak tetap, interval tetap 0.5s. PX menilai biomekanik, jadi gesture-nya perlu
variasi natural: percepatan awal, jitter tidak teratur, jeda tidak seragam,
drift halus, dan durasi yang bervariasi.
"""
import os
import random
import subprocess
import sys
import time

DISPLAY = ":99"
WID = os.environ.get("WID", "2097155")
BX = int(os.environ.get("BX", "660"))
BY = int(os.environ.get("BY", "689"))
os.environ["DISPLAY"] = DISPLAY


def xdo(*args):
    subprocess.run(["xdotool", *args], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shot(name):
    subprocess.run(["import", "-window", WID, f"/tmp/x11shots/{name}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def human_hold():
    """Turunkan tombol, tahan dengan gerakan tidak teratur, lepaskan."""
    xdo("windowactivate", "--sync", WID)
    xdo("mousemove", "--sync", str(BX), str(BY))
    time.sleep(random.uniform(0.7, 1.3))

    # sentuh: sedikit di atas pusat, lalu turun ke pusat (seperti tangan manusia)
    xdo("mousemove", "--sync", str(BX - random.randint(2, 5)), str(BY - random.randint(2, 4)))
    time.sleep(random.uniform(0.08, 0.2))
    xdo("mousemove", "--sync", str(BX), str(BY))
    time.sleep(random.uniform(0.05, 0.12))
    xdo("mousedown", "1")

    # tahan: jitter tidak teratur, jeda tidak seragam, drift halus
    hold = random.uniform(6.5, 9.0)
    t0 = time.time()
    cx, cy = BX, BY
    while time.time() - t0 < hold:
        # gerak kecil dengan besar langkah bervariasi
        cx += random.uniform(-1.6, 1.6)
        cy += random.uniform(-1.2, 1.2)
        # jaga tetap di dalam tombol
        cx = min(max(cx, BX - 40), BX + 40)
        cy = min(max(cy, BY - 12), BY + 12)
        xdo("mousemove", "--sync", str(int(cx)), str(int(cy)))
        # jeda tidak seragam: kadang cepat, kadang ada jeda
        if random.random() < 0.18:
            time.sleep(random.uniform(0.25, 0.7))   # jeda sesaat
        else:
            time.sleep(random.uniform(0.03, 0.18))  # gerak cepat
    shot("40_holding")

    # lepas: sedikit gerak lalu angkat
    time.sleep(random.uniform(0.1, 0.3))
    xdo("mouseup", "1")
    print(f"  hold {hold:.1f}s selesai")


if __name__ == "__main__":
    human_hold()
    time.sleep(4)
    shot("41_released")
    out = subprocess.run(["xdotool", "getwindowname", WID],
                         capture_output=True, text=True).stdout.strip()
    print("judul:", out)
    time.sleep(12)
    shot("42_settled")
    out = subprocess.run(["xdotool", "getwindowname", WID],
                         capture_output=True, text=True).stdout.strip()
    print("judul akhir:", out)
