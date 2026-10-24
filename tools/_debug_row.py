#!/usr/bin/env python3
"""Debug mengapa pemindaian tombol mengembalikan 0 kandidat pada baris y=689."""
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"
Y = int(sys.argv[2]) if len(sys.argv) > 2 else 689

out = subprocess.run(["convert", SRC, "-colorspace", "Gray", "-depth", "8", "txt:-"],
                     capture_output=True, text=True).stdout
rows = {}
for line in out.splitlines()[1:]:
    try:
        x, rest = line.split(",")
        y = int(rest.split(":")[0])
        v = int(float(line.split("(")[1].split(",")[0])) / 255.0
        rows.setdefault(y, []).append((int(x), v))
    except Exception:
        continue

print("jumlah baris terbaca:", len(rows))
px = rows.get(Y, [])
print(f"baris {Y}: {len(px)} piksel")
dark = [x for x, v in px if v < 0.72]
print(f"  gelap (v<0.72): {len(dark)} -> x {min(dark) if dark else '-'}..{max(dark) if dark else '-'}")
if dark:
    x0, x1 = min(dark), max(dark)
    print(f"  lebar = {x1 - x0} (perlu 200..340)")
    inner = [v for x, v in px if x0 + 6 < x < x1 - 6]
    if inner:
        print(f"  rata-rata isi = {sum(inner)/len(inner):.3f} (perlu > 0.88)")
        print(f"  jumlah piksel isi = {len(inner)}")
