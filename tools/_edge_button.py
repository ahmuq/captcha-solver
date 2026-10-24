#!/usr/bin/env python3
"""Cari tombol press-and-hold: pill putih ber-outline, di bawah grafik tantangan.

Tombolnya TIDAK biru (outline abu #707070, teks biru tipis), jadi mask biru gagal.
Pendekatan: cari baris yang mengandung dua tepi vertikal (outline kiri & kanan)
berjarak lebar tombol (~250-300 px), lalu ambil kandidat paling bawah.
"""
import os
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"
pid = os.getpid()
tmp = f"/tmp/_edge_{pid}.png"


def c(*a):
    return subprocess.run(["convert", *a], capture_output=True, text=True)


# tepi horizontal: gradien lalu threshold
c(SRC, "-colorspace", "Gray", "-define", "convolve:scale=1",
  "-morphology", "Convolve", "Sobel:0,1,0,1,-4,1,0,1,0",
  "-threshold", "40%", tmp)

txt = c(tmp, "-depth", "8", "txt:-").stdout
rows = {}
for line in txt.splitlines()[1:]:
    try:
        x, rest = line.split(",")
        y = int(rest.split(":")[0])
        v = int(float(line.split("(")[1].split(")")[0].split(",")[0]))
        if v > 128:
            rows.setdefault(y, []).append(int(x))
    except Exception:
        continue

print("baris dengan tepi kuat, lebar rentang > 200 px (kandidat tombol):")
cands = []
for y in sorted(rows):
    xs = rows[y]
    if len(xs) >= 2 and (max(xs) - min(xs)) > 200:
        cands.append((y, min(xs), max(xs), len(xs)))
for y, x0, x1, n in cands:
    print(f"  y={y:4} x={x0:4}..{x1:4} (lebar {x1-x0:4}, {n} titik tepi)")
if cands:
    y = cands[-1][0]
    print(f"\nkandidat terbawah (paling mungkin tombol): y={y}, "
          f"pusat x={(cands[-1][1]+cands[-1][2])//2}")
