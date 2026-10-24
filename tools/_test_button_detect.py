#!/usr/bin/env python3
"""Uji fungsi deteksi tombol pada screenshot gate nyata (tanpa browser).

Memanggil logika yang sama dengan sessionless.py terhadap /tmp/x11fresh/G0_fresh_gate.png
supaya deteksi tombol terbukti, bukan diasumsikan.
"""
import os
import subprocess
import sys

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"


class FakeBrowser:
    """Cukup untuk _find_gate_button: hanya butuh .screenshot(path, wid)."""

    def __init__(self, src):
        self.src = src

    def screenshot(self, path, wid=None):
        subprocess.run(["cp", self.src, path], check=True)
        return True


from perimeterx.sessionless import _find_gate_button   # noqa: E402

box = _find_gate_button(FakeBrowser(SRC), "fake")
print(f"screenshot : {SRC}")
if box:
    print(f"tombol     : ({box[0]}, {box[1]})")
    # bandingkan dengan posisi yang sudah terbukti dari percobaan sebelumnya
    print(f"referensi  : (660, 689) — posisi yang dipakai saat gate naik")
    dx, dy = box[0] - 660, box[1] - 689
    print(f"selisih    : dx={dx} dy={dy}")
else:
    print("tombol     : TIDAK terdeteksi")
    sys.exit(1)
