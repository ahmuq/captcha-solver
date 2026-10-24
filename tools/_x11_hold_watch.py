#!/usr/bin/env python3
"""Tahan tombol gate PX SAMBIL memantau: berapa lama sampai PX menilai.

Sinyal terukur:
  * saat ditahan, tombol menampilkan 3 titik = PX sedang memproses (PoW).
  * lepas terlalu cepat -> tidak ada error, tidak ada hasil (persis yang terjadi).
Skrip ini menahan selama mungkin sambil merekam hash region tombol tiap 2s, supaya
kelihatan kapan state-nya berubah (progress / sukses / error), lalu baru lepas.
"""
import hashlib
import os
import random
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11shots"
MAX_HOLD = float(os.environ.get("MAX_HOLD", "45"))
BX = int(os.environ.get("BX", "660"))
BY = int(os.environ.get("BY", "689"))


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_wid():
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if not m:
            continue
        a = int(m.group(1)) * int(m.group(2))
        if a > a0:
            best, a0 = w, a
    return best


WID = find_wid()
print("WID:", WID, "|", run("xdotool", "getwindowname", WID))
if "prove" not in run("xdotool", "getwindowname", WID).lower():
    print("halaman bukan gate PX — berhenti")
    sys.exit(3)


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def btn_hash(tag):
    """Hash region tombol (520..800 x, 655..725 y) untuk mendeteksi perubahan visual."""
    p = f"/tmp/_btn_{tag}.png"
    subprocess.run(["convert", f"{SHOTS}/{tag}.png", "-crop", "280x70+520+655", "+repage", p],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:10]
    except Exception:
        return "n/a"


xdo("windowactivate", WID)
time.sleep(0.6)

# approach ke tombol
out = run("xdotool", "getmouselocation")
sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
for i in range(1, 23):
    t = i / 22; e = 1 - (1 - t) ** 2.2
    xdo("mousemove", str(int(sx + (BX - sx) * e)), str(int(sy + (BY - sy) * e)))
    time.sleep(random.uniform(0.012, 0.03))
xdo("mousemove", str(BX), str(BY))
time.sleep(0.5)
shot("M0_idle")
print("idle btn hash:", btn_hash("M0_idle"))

xdo("mousedown", "1")
print(f"  mousedown — tahan maks {MAX_HOLD}s, pantau tiap 2s")
t0 = time.time()
cx, cy = float(BX), float(BY)
last = None
i = 0
while time.time() - t0 < MAX_HOLD:
    cx = min(max(cx + random.uniform(-1.3, 1.3), BX - 18), BX + 18)
    cy = min(max(cy + random.uniform(-0.9, 0.9), BY - 5), BY + 5)
    xdo("mousemove", str(int(cx)), str(int(cy)))
    i += 1
    time.sleep(random.uniform(0.03, 0.14) if random.random() > 0.15
               else random.uniform(0.2, 0.45))

    el = time.time() - t0
    if i % 25 == 0:
        tag = f"M_hold_{int(el):02d}s"
        shot(tag)
        h = btn_hash(tag)
        t = title()
        flag = "  <-- BERUBAH" if (last and h != last) else ""
        print(f"  t={el:5.1f}s hash={h} judul={t[:40]!r}{flag}")
        last = h
        if "prove" not in t.lower():
            print("  >>> judul berubah — lepas")
            break

xdo("mouseup", "1")
el = time.time() - t0
print(f"  mouseup setelah {el:.1f}s")
shot("M_released")
time.sleep(4)
print("judul 4s:", title())
shot("M_after4")
time.sleep(12)
print("judul 16s:", title())
shot("M_final")