#!/usr/bin/env python3
"""Debug: tampilkan pita-pita biru yang ditemukan pada screenshot gate."""
import os
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"
pid = os.getpid()
tr, tb, tm = f"/tmp/_d_r{pid}.png", f"/tmp/_d_b{pid}.png", f"/tmp/_d_m{pid}.png"


def c(*a):
    return subprocess.run(["convert", *a], capture_output=True, text=True)


c(SRC, "-channel", "R", "-separate", "+channel", tr)
c(SRC, "-channel", "B", "-separate", "+channel", tb)
c(tb, tr, "-compose", "minus", "-composite", "-threshold", "12%", tm)

txt = c(tm, "-resize", "1x900!", "-depth", "8", "txt:-").stdout
dens = {}
for line in txt.splitlines()[1:]:
    try:
        y = int(line.split(",")[1].split(":")[0])
        v = int(float(line.split("(")[1].split(")")[0].split(",")[0]))
        dens[y] = v
    except Exception:
        continue

print("y dengan kerapatan > 0 (dari y=600 ke bawah):")
for y in range(400, 900):
    v = dens.get(y, 0)
    if v:
        print(f"  y={y:4} dens={v:4}  {'#' * min(v, 60)}")
