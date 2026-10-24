#!/usr/bin/env python3
"""Kapan PX menolak hold? Bandingkan strip di bawah tombol (tempat teks error muncul)
dan region tombol, lintas semua screenshot selama hold."""
import glob
import hashlib
import os
import re
import subprocess

SHOTS = "/tmp/x11shots"


def crop_hash(src, geom, tag):
    p = f"/tmp/_c_{tag}.png"
    r = subprocess.run(["convert", src, "-crop", geom, "+repage", p],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "ERR"
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


files = sorted(glob.glob(f"{SHOTS}/M_hold_*.png"),
               key=lambda p: int(re.search(r"_(\d+)s", p).group(1)))
files = [f"{SHOTS}/M0_idle.png"] + files + [f"{SHOTS}/M_released.png", f"{SHOTS}/M_final.png"]

print(f"{'file':28} {'btn':12} {'err_strip':12}")
base_err = None
for f in files:
    n = os.path.basename(f)
    b = crop_hash(f, "280x70+520+655", n + "_b")
    e = crop_hash(f, "520x45+500+728", n + "_e")
    if base_err is None:
        base_err = e
    mark = "  <-- ERROR MUNCUL" if e != base_err and e != "ERR" else ""
    print(f"{n:28} {b:12} {e:12}{mark}")
