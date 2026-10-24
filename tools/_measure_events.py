#!/usr/bin/env python3
"""Ukur berapa event XTest yang BENAR-BENAR terkirim saat press-and-hold.

Kecurigaan: `_emit` membuang event kalau posisi tidak berubah setelah pembulatan
integer, sementara tremor 0.3-1.2 px dikali 0.55 jadi 0.16-0.66 px — sub-pixel. Angka
"88 Hz" di log menghitung iterasi loop (n += 1), bukan event nyata. Kalau event nyata
jauh lebih sedikit, browser melihat pointer hampir diam -> PX menandai bot.
"""
import os
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx import x11 as X11   # noqa: E402

hand = X11.Hand()
real = [0]
orig = hand._emit


def counting_emit(x, y):
    before = (hand._lx, hand._ly)
    orig(x, y)
    if (hand._lx, hand._ly) != before:
        real[0] += 1


hand._emit = counting_emit

hand.move_instant(640, 300)
real[0] = 0
t0 = time.perf_counter()
hand.press()
held = time.perf_counter() - t0
# jalankan loop hold 3 detik persis seperti press_and_hold
loop_n = 0
t0 = time.perf_counter()
while time.perf_counter() - t0 < 3.0:
    el = time.perf_counter() - t0
    tx, ty = hand._tremor(el)
    dx, dy = hand._drift_step()
    hand._emit(640 + (tx + dx) * 0.55, 300 + (ty + dy) * 0.55)
    loop_n += 1
    hand.d.sync()
    time.sleep(X11.DT)
held = time.perf_counter() - t0
hand.release()

print(f"durasi            : {held:.2f}s")
print(f"iterasi loop      : {loop_n}  ({loop_n/held:.0f} Hz)  <- angka yang dilaporkan log")
print(f"event XTest NYATA : {real[0]}  ({real[0]/held:.0f} Hz)  <- yang dilihat browser")
print(f"rasio             : {100*real[0]/max(loop_n,1):.0f}%")
print()
print("amplitudo tremor  :", [round(a, 2) for a in hand._ta], "px  (x0.55 =",
      [round(a * 0.55, 2) for a in hand._ta], "px)")
print("frekuensi tremor  :", hand._tf, "Hz")
