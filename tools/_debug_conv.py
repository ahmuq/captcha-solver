#!/usr/bin/env python3
"""Uji mengapa subprocess convert tidak mengembalikan piksel."""
import subprocess

SRC = "/tmp/x11fresh/G0_fresh_gate.png"
r = subprocess.run(["convert", SRC, "-colorspace", "Gray", "-depth", "8", "txt:-"],
                   capture_output=True, text=True)
print("returncode:", r.returncode)
print("stdout len:", len(r.stdout))
print("stderr:", r.stderr[:300])
print("stdout head:")
print(r.stdout[:200])

# bandingkan tanpa -depth
r2 = subprocess.run(["convert", SRC, "-colorspace", "Gray", "txt:-"],
                    capture_output=True, text=True)
print("\ntanpa -depth -> stdout len:", len(r2.stdout), "rc:", r2.returncode)
print(r2.stdout[:160])
