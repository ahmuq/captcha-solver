#!/usr/bin/env python3
"""Jalankan loop: rotasi IP -> jeda -> walk -> hold, sampai gate lolos atau N habis."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hloop import log, rotate, launch, GAP, N
from _hloop_walk import walk, hold


for i in range(1, N + 1):
    log(f"\n========== SESI {i}/{N} ==========")
    ip = rotate()
    log(f"IP HP baru: {ip}")
    if i > 1:
        log(f"jeda {GAP:.0f}s sebelum sesi berikutnya (hindari velocity signup)")
        time.sleep(GAP)
    WID = launch()
    if not WID:
        log("window tidak ketemu"); continue
    log(f"WID: {WID}")
    t = walk(WID, f"s{i}")
    if "prove" not in t.lower():
        log(f"[s{i}] tidak ada gate: {t} — lanjut sesi berikutnya")
        continue
    t = hold(WID, f"s{i}")
    if "prove" not in t.lower():
        log(f"[s{i}] >>> LOLOS dari gate: {t}")
        sys.exit(0)
    log(f"[s{i}] masih di gate")

log("\nselesai: belum lolos")
