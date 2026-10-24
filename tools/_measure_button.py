#!/usr/bin/env python3
"""Ukur warna tombol press-and-hold dari screenshot gate nyata.

Screenshot gate nyata ada di /tmp/x11fresh/G0_fresh_gate.png. Ambil warna dominan
di area tombol supaya mask di sessionless.py memakai warna yang benar, bukan tebakan.
"""
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"
# area tombol pada layout 1280x900 (dari analisis visual sebelumnya)
CROP = "300x90+500+645"

out = subprocess.run(["convert", SRC, "-crop", CROP, "+repage", "-format", "%c",
                      "-colors", "8", "histogram:info:-"],
                     capture_output=True, text=True)
print("=== warna dominan di area tombol ===")
print(out.stdout[:1200])

out2 = subprocess.run(["convert", SRC, "-crop", CROP, "+repage",
                       "-resize", "1x1", "-format", "%[pixel:p{0,0}]", "info:"],
                      capture_output=True, text=True)
print("rata-rata area tombol:", out2.stdout.strip())

# cari baris yang paling "biru" untuk memastikan posisi vertikal tombol
out3 = subprocess.run(["convert", SRC, "-crop", "1280x1+0+660", "+repage",
                       "-resize", "1x1", "-format", "%[pixel:p{0,0}]", "info:"],
                      capture_output=True, text=True)
print("rata-rata baris y=660:", out3.stdout.strip())
