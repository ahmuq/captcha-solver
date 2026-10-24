#!/usr/bin/env python3
"""Cari tombol lewat profil baris: hitung piksel biru per baris, ambil puncaknya.

Tombol press-and-hold adalah elemen biru terbesar di kartu, jadi barisnya akan
mencolok dibanding baris lain. Ini lebih tahan-banting daripada connected-components
pada gambar yang penuh gradien.
"""
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"

# Untuk setiap baris, hitung jumlah piksel biru (b - r > 0.12) memakai -fx per baris
# terlalu lambat; pakai trik: pisahkan kanal, threshold, lalu rata-ratakan per baris.
cmds = [
    ["convert", SRC, "-channel", "R", "-separate", "+channel", "/tmp/_r.png"],
    ["convert", SRC, "-channel", "B", "-separate", "+channel", "/tmp/_b.png"],
]
for c in cmds:
    subprocess.run(c, check=True, capture_output=True)

# biru - merah > 0.12  ->  mask
subprocess.run(["convert", "/tmp/_b.png", "/tmp/_r.png", "-compose", "minus",
                "-composite", "-threshold", "12%", "/tmp/_mask.png"],
               check=True, capture_output=True)

# rata-rata per baris (skala 1x900)
out = subprocess.run(["convert", "/tmp/_mask.png", "-resize", "1x900!",
                      "-depth", "8", "txt:-"], capture_output=True, text=True).stdout
rows = []
for line in out.splitlines()[1:]:
    try:
        y = int(line.split(",")[1].split(":")[0])
        val = line.split("(")[1].split(")")[0].split(",")[0]
        rows.append((int(float(val)), y))
    except Exception:
        continue
rows.sort(reverse=True)
print("baris paling biru (nilai, y):")
for v, y in rows[:12]:
    print(f"   y={y:4}  kerapatan={v}")

# ambil puncak, lalu lebar tombol pada baris itu
if rows:
    ybest = rows[0][1]
    out2 = subprocess.run(["convert", "/tmp/_mask.png", "-crop", f"1280x1+0+{ybest}",
                           "+repage", "txt:-"], capture_output=True, text=True).stdout
    xs = []
    for line in out2.splitlines()[1:]:
        try:
            x = int(line.split(",")[0])
            val = int(float(line.split("(")[1].split(")")[0].split(",")[0]))
            if val > 128:
                xs.append(x)
        except Exception:
            continue
    if xs:
        print(f"\ntombol pada y={ybest}: x dari {min(xs)} sampai {max(xs)} "
              f"(pusat x={(min(xs)+max(xs))//2})")
