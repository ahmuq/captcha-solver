#!/usr/bin/env python3
"""Uji hipotesis: gate terkunci setelah beberapa percobaan gagal.

Reload halaman, lalu cek apakah tombol kembali responsif (hover bereaksi).
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


xdo("windowactivate", WID)
time.sleep(0.5)
print("judul sebelum reload:", run("xdotool", "getwindowname", WID))

# Ctrl+R
xdo("key", "ctrl+r")
time.sleep(10)
print("judul setelah reload:", run("xdotool", "getwindowname", WID))
shot("90_after_reload")

# hover ke area tombol untuk cek responsivitas
xdo("mousemove", "660", "689")
time.sleep(2)
shot("91_hover_after_reload")

# klik "Accessible challenge" (sekitar x=500)
xdo("mousemove", "500", "689")
time.sleep(0.8)
xdo("click", "1")
time.sleep(5)
shot("92_accessible_after_reload")
print("judul setelah klik accessible:", run("xdotool", "getwindowname", WID))
