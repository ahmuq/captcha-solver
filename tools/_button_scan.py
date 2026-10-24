#!/usr/bin/env python3
"""Deteksi tombol dengan pendekatan yang dapat diandalkan.

Temuan: tombolnya pill PUTIH dengan outline abu (#707070) dan teks biru tipis.
Mask warna gagal karena latar kartu juga putih. Tapi ada satu ciri yang khas:
baris tombol punya *tepi vertikal gelap* (outline) di kiri dan kanan, berjarak ~250 px,
dan di antara keduanya warnanya putih merata.

Jadi: untuk setiap baris y, cari pasangan piksel gelap (V < 0.65) yang berjarak
200-340 px, dan antar keduanya rata-rata kecerahan > 0.9 (isi putih). Kandidat
terbawah = tombol.
"""
import os
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"
pid = os.getpid()
gray = f"/tmp/_g_{pid}.png"


def c(*a):
    return subprocess.run(["convert", *a], capture_output=True, text=True)


c(SRC, "-colorspace", "Gray", "-depth", "8", gray)
txt = c(gray, "-depth", "8", "txt:-").stdout

# bangun baris -> daftar (x, v)
rows = {}
for line in txt.splitlines()[1:]:
    try:
        x, rest = line.split(",")
        y = int(rest.split(":")[0])
        v = int(float(line.split("(")[1].split(")")[0].split(",")[0])) / 255.0
        rows.setdefault(y, []).append((int(x), v))
    except Exception:
        continue

hits = []
for y in sorted(rows):
    if y < 400:
        continue
    px = rows[y]
    dark = [x for x, v in px if v < 0.65]
    if len(dark) < 2:
        continue
    x0, x1 = min(dark), max(dark)
    width = x1 - x0
    if not (200 <= width <= 340):
        continue
    inner = [v for x, v in px if x0 + 6 < x < x1 - 6]
    if not inner:
        continue
    if sum(inner) / len(inner) > 0.88:          # isi putih
        hits.append((y, x0, x1, round(sum(inner) / len(inner), 3)))

print(f"kandidat baris tombol: {len(hits)}")
for h in hits[:6]:
    print("   ", h)
for h in hits[-6:]:
    print("   ", h)
if hits:
    y, x0, x1, _ = hits[-1]
    print(f"\n=> tombol: y={y}, pusat x={(x0+x1)//2}")
