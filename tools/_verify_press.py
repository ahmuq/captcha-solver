#!/usr/bin/env python3
"""Apakah hold benar-benar mengirim ButtonPress/ButtonRelease ke window?

Tombol yang tidak bereaksi bisa berarti eventnya tidak pernah terkirim, atau
terkirim ke tempat yang salah. Uji: kirim press+hold+release, lalu baca state
tombol dari X server (tombol mouse mana yang ditekan) di tengah hold.

Juga: bandingkan hasil bila window difokuskan dulu (XSetInputFocus) — window yang
tidak fokus bisa mengabaikan input di beberapa setup.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from Xlib import display as xdisplay, X            # noqa: E402
from perimeterx.x11 import Hand                    # noqa: E402

d = xdisplay.Display(":99")


def mouse_buttons():
    """Mask tombol mouse yang SEDANG ditekan (bit 8..15)."""
    q = d.screen().root.query_pointer()
    return q.mask & 0x1F00


hand = Hand()
print("=== sebelum press ===")
print(f"  mask tombol: {mouse_buttons():#x}")

# Fokuskan window browser dulu
out = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "PX Host"],
                     capture_output=True, text=True,
                     env={**os.environ, "DISPLAY": ":99"}).stdout.split()
if out:
    wid = out[-1]
    subprocess.run(["xdotool", "windowactivate", "--sync", wid],
                   capture_output=True, text=True,
                   env={**os.environ, "DISPLAY": ":99"})
    subprocess.run(["xdotool", "windowfocus", wid], capture_output=True, text=True,
                   env={**os.environ, "DISPLAY": ":99"})
    time.sleep(0.6)
    print(f"  window difokuskan: {wid}")

hand.move_instant(640, 300)
time.sleep(0.3)

print("\n=== saat press ===")
hand.press()
time.sleep(0.3)
mb = mouse_buttons()
print(f"  mask tombol: {mb:#x}  -> Button1 {'DITEKAN' if mb & 0x100 else 'TIDAK ditekan'}")

# Gerakkan sedikit selama hold (uji apakah event motion sampai)
for i in range(6):
    hand._emit(640 + (i % 3) - 1, 300 + (i % 2))
    hand.d.sync()
    time.sleep(0.15)

print("\n=== saat release ===")
hand.release()
time.sleep(0.3)
mb = mouse_buttons()
print(f"  mask tombol: {mb:#x}  -> Button1 {'MASIH ditekan' if mb & 0x100 else 'sudah dilepas'}")

# Cek pointer sekarang
q = d.screen().root.query_pointer()
print(f"\nposisi pointer: ({q.root_x},{q.root_y})  child={q.child}")
print(f"fokus window  : {d.get_input_focus().focus}")
