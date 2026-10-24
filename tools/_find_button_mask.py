#!/usr/bin/env python3
"""Cari deteksi tombol yang benar: tombol = outline biru + teks biru, isinya putih.

Uji beberapa mask pada screenshot gate nyata dan lihat komponen mana yang muncul.
"""
import subprocess
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh/G0_fresh_gate.png"


def components(mask_expr, label, area=1500):
    out = subprocess.run(
        ["convert", SRC, "-fx", mask_expr, "-threshold", "50%",
         "-define", "connected-components:verbose=true",
         f"-define", f"connected-components:area-threshold={area}",
         "-connected-components", "8", "null:"],
        capture_output=True, text=True)
    print(f"=== {label} ===")
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    for l in lines[:12]:
        print("   ", l.strip())
    if not lines:
        print("    (tidak ada komponen)")
    print()


# 1. biru jelas lebih dominan dari merah (outline/teks biru)
components("(b-r>0.15 && b>0.35) ? 1 : 0", "mask: b-r>0.15")
# 2. lebih longgar
components("(b-r>0.08 && b>0.3) ? 1 : 0", "mask: b-r>0.08")
