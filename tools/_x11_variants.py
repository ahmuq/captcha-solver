#!/usr/bin/env python3
"""Coba beberapa variasi gesture press-and-hold, catat mana yang diterima PX.

Diagnostik: hitung iterasi & simpan screenshot tiap varian, supaya tidak menebak.
"""
import os
import random
import subprocess
import time

DISPLAY = ":99"
WID = os.environ.get("WID", "2097155")
BX = int(os.environ.get("BX", "660"))
BY = int(os.environ.get("BY", "689"))
os.environ["DISPLAY"] = DISPLAY


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return subprocess.run(["xdotool", "getwindowname", WID],
                          capture_output=True, text=True).stdout.strip()


def shot(name):
    r = subprocess.run(["import", "-window", WID, f"/tmp/x11shots/{name}.png"],
                       capture_output=True, text=True)
    return r.returncode == 0


def hold_clean(seconds):
    """Tanpa micro-movement sama sekali."""
    xdo("mousemove", "--sync", str(BX), str(BY))
    time.sleep(0.8)
    xdo("mousedown", "1")
    time.sleep(seconds)
    xdo("mouseup", "1")


def hold_drift(seconds):
    """Drift halus: gerak lambat satu arah, seperti tangan yang lelah."""
    xdo("mousemove", "--sync", str(BX), str(BY))
    time.sleep(0.8)
    xdo("mousedown", "1")
    t0 = time.time()
    cx, cy = float(BX), float(BY)
    it = 0
    while time.time() - t0 < seconds:
        cx += random.uniform(-0.5, 0.5)
        cy += random.uniform(-0.3, 0.3)
        cx = min(max(cx, BX - 8), BX + 8)
        cy = min(max(cy, BY - 4), BY + 4)
        xdo("mousemove", "--sync", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.06, 0.22))
    print(f"    (drift iterasi={it})")
    xdo("mouseup", "1")


VARIANTS = [
    ("clean_8s", lambda: hold_clean(8)),
    ("clean_15s", lambda: hold_clean(15)),
    ("drift_12s", lambda: hold_drift(12)),
    ("clean_25s", lambda: hold_clean(25)),
]


def main():
    for name, fn in VARIANTS:
        print(f"=== VARIAN: {name} ===")
        print("  judul sebelum:", title())
        fn()
        time.sleep(3)
        ok = shot(f"60_{name}_released")
        print(f"  judul setelah lepas: {title()!r} (shot={ok})")
        time.sleep(8)
        shot(f"61_{name}_settled")
        t = title()
        print(f"  judul akhir: {t!r}")
        if "prove" not in t.lower():
            print("  >>> LOLOS! judul berubah")
            break
        # siapkan percobaan berikutnya: klik ulang area tombol kalau perlu
        xdo("windowactivate", "--sync", WID)
        time.sleep(1)


if __name__ == "__main__":
    main()
