#!/usr/bin/env python3
"""Apakah klik benar-benar mendarat di window browser?

Screenshot diambil per window ID (`import -window <id>`), jadi ia bisa menampilkan
window yang benar WALAU window lain menutupinya di layar. Kalau begitu, klik di
koordinat tombol mendarat di window lain dan tombolnya tidak akan bereaksi.

Uji: luncurkan browser non-CDP, deteksi tombol, lalu tanya X server window mana yang
berada di bawah kursor pada titik itu, dan bandingkan dengan window browser kita.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser                    # noqa: E402
from perimeterx.sessionless import _Wrapper, _find_gate_button  # noqa: E402
from perimeterx.x11 import Hand                           # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
SID = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-4000-8000-000000000003"
UUID = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-4000-8000-000000000002"
VID = sys.argv[3] if len(sys.argv) > 3 else "00000000-0000-4000-8000-000000000001"


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True,
                          env={**os.environ, "DISPLAY": ":99"}).stdout.strip()


profile = f"/tmp/_click_{int(time.time())}"
wrap = _Wrapper(f"https://iframe.hsprotect.net/index.html?app_id={APP}&session_id={SID}",
                UUID, VID)
br = Browser(profile, proxy=PROXY)
try:
    br.start(wrap.url, 20.0)
    wid = br.window_id()
    print(f"window browser (wid) : {wid}")
    print(f"geometry             : {sh('xdotool', 'getwindowgeometry', wid)}")

    box = _find_gate_button(br, wid, br.height)
    print(f"tombol terdeteksi    : {box}")
    if not box:
        print("tombol tidak ketemu"); raise SystemExit(1)
    bx, by = box

    # Daftar SEMUA window + urutan tumpukan (yang teratas lebih dulu)
    print("\n=== semua window (urutan tumpukan) ===")
    ids = sh("xdotool", "search", "--onlyvisible", "--name", "").split()
    for i, w in enumerate(ids[:12]):
        nm = sh("xdotool", "getwindowname", w)[:40]
        geo = sh("xdotool", "getwindowgeometry", w).replace("\n", " | ")[:70]
        print(f"  [{i}] {w}  {nm!r}\n       {geo}")

    # Pindahkan kursor ke tombol, lalu tanya window mana yang ada di bawahnya
    hand = Hand()
    hand.move_instant(bx, by)
    time.sleep(0.4)
    loc = sh("xdotool", "getmouselocation", "--shell")
    print("\n=== posisi kursor ===")
    print(loc.replace("\n", "  "))
    under = ""
    for line in loc.splitlines():
        if line.startswith("WINDOW="):
            under = line.split("=", 1)[1]
    print(f"\nwindow DI BAWAH KURSOR : {under}")
    print(f"window browser kita    : {wid}")
    print(f"COCOK?                 : {'YA' if under == wid else 'TIDAK — klik mendarat di window lain!'}")
    if under and under != wid:
        print(f"  nama window itu: {sh('xdotool', 'getwindowname', under)!r}")
        print(f"  geometry       : {sh('xdotool', 'getwindowgeometry', under)}")
finally:
    br.stop()
    wrap.close()
    subprocess.run(["rm", "-rf", profile], check=False)
