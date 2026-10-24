#!/usr/bin/env python3
"""Press-and-hold dengan pemantauan progres: tahan lama sambil screenshot berkala.

Hipotesis: saat ditahan, tombol menampilkan state loading (PoW sedang jalan). Rilis
di detik 8 mungkin terlalu cepat. Skrip ini menahan sampai 30s sambil memantau judul
jendela dan mengambil screenshot tiap 2s, supaya kelihatan kapan tantangan selesai.
"""
import os
import random
import subprocess
import time

DISPLAY = ":99"
WID = os.environ.get("WID", "2097155")
BX = int(os.environ.get("BX", "660"))
BY = int(os.environ.get("BY", "689"))
MAX_HOLD = float(os.environ.get("MAX_HOLD", "30"))
os.environ["DISPLAY"] = DISPLAY


def xdo(*args):
    subprocess.run(["xdotool", *args], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return subprocess.run(["xdotool", "getwindowname", WID],
                          capture_output=True, text=True).stdout.strip()


def shot(name):
    subprocess.run(["import", "-window", WID, f"/tmp/x11shots/{name}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    print("judul awal:", title())
    xdo("windowactivate", "--sync", WID)
    xdo("mousemove", "--sync", str(BX), str(BY))
    time.sleep(1.0)

    xdo("mousedown", "1")
    print(f"  mousedown @ {BX},{BY} — menahan sampai {MAX_HOLD}s (pantau tiap 2s)")
    t0 = time.time()
    cx, cy = BX, BY
    n = 0
    while time.time() - t0 < MAX_HOLD:
        # tremor halus: amplitudo kecil, jeda tidak seragam
        cx = min(max(cx + random.uniform(-1.2, 1.2), BX - 25), BX + 25)
        cy = min(max(cy + random.uniform(-0.9, 0.9), BY - 8), BY + 8)
        xdo("mousemove", "--sync", str(int(cx)), str(int(cy)))
        time.sleep(random.uniform(0.04, 0.16))
        n += 1
        elapsed = time.time() - t0
        if n % 20 == 0:
            shot(f"50_hold_{int(elapsed):02d}s")
            t = title()
            print(f"  t={elapsed:4.1f}s judul={t!r}")
            if "prove" not in t.lower():
                print("  >>> judul berubah — tantangan mungkin selesai, lepas")
                break
    xdo("mouseup", "1")
    print("  mouseup")
    time.sleep(3)
    shot("51_released")
    print("judul setelah lepas:", title())
    time.sleep(10)
    shot("52_settled")
    print("judul akhir:", title())


if __name__ == "__main__":
    main()
