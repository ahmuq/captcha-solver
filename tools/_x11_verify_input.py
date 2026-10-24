#!/usr/bin/env python3
"""Verifikasi apakah event X11 benar-benar sampai ke halaman gate.

1. Geometri jendela + posisi pointer (konfirmasi pemetaan koordinat).
2. Hover ke tombol -> screenshot (kalau ada perubahan visual, koordinat benar).
3. Klik elemen yang efeknya jelas ("Accessible challenge") -> lihat apakah halaman bereaksi.
"""
import os
import subprocess
import time

os.environ["DISPLAY"] = ":99"
WID = os.environ.get("WID", "2097155")


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shot(n):
    subprocess.run(["import", "-window", WID, f"/tmp/x11shots/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  shot: {n}")


print("=== geometri jendela ===")
print(run("xdotool", "getwindowgeometry", WID))
print("=== posisi pointer awal ===")
print(run("xdotool", "getmouselocation"))

print("\n=== uji 1: hover ke tombol (660,689) ===")
xdo("mousemove", "660", "689")
time.sleep(1.5)
print("  pointer:", run("xdotool", "getmouselocation"))
shot("80_hover_button")

print("\n=== uji 2: hover ke luar tombol (400,300) ===")
xdo("mousemove", "400", "300")
time.sleep(1.5)
shot("81_hover_away")

print("\n=== uji 3: klik 'Accessible challenge' (efek harus jelas) ===")
print("  judul sebelum:", run("xdotool", "getwindowname", WID))
xdo("mousemove", "500", "689")
time.sleep(0.8)
xdo("click", "1")
time.sleep(4)
shot("82_after_accessible_click")
print("  judul setelah:", run("xdotool", "getwindowname", WID))
