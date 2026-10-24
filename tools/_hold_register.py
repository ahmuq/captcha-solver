#!/usr/bin/env python3
"""Apakah press-and-hold benar-benar TERDAFTAR oleh PX?

Ambil screenshot SELAMA hold (0.5s/2s/4s/6s) dan bandingkan dengan baseline sebelum
hold. Kalau diff = 0 di semua frame, mousedown tidak sampai ke elemen tombol — jadi
masalahnya bukan biomekanik, melainkan eventnya tidak pernah "mendarat".

Sekaligus uji dua posisi tekan: tengah pill dan di ikon bulat (UI asli biasanya
menekan ikonnya).
"""
import json
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


def shot_diff(a, b):
    """Jumlah piksel berbeda antara dua PNG (0 = identik).

    ImageMagick menulis metrik ke STDERR, bukan stdout — membaca stdout selalu
    menghasilkan -1 dan menyamarkan perubahan nyata sebagai "tidak ada diff".
    """
    r = subprocess.run(["compare", "-metric", "AE", a, b, "null:"],
                       capture_output=True, text=True)
    txt = (r.stderr or r.stdout or "").strip()
    try:
        return int(float(txt.split()[0]))
    except Exception:
        return -1


profile = f"/tmp/_hold_{int(time.time())}"
wrap = _Wrapper(f"https://iframe.hsprotect.net/index.html?app_id={APP}&session_id={SID}",
                UUID, VID)
br = Browser(profile, proxy=PROXY)
hand = Hand()
try:
    br.start(wrap.url, 20.0)
    wid = br.window_id()
    if not wid:
        print("window tidak ketemu"); raise SystemExit(1)

    t0 = time.time()
    while time.time() - t0 < 30 and not wrap.rendered.is_set():
        time.sleep(1)
    print(f"rendered: {wrap.rendered.is_set()}")

    box = _find_gate_button(br, wid, br.height)
    print(f"tombol: {box}")
    if not box:
        raise SystemExit("tombol tidak ketemu")
    bx, by = box

    base = "/tmp/_hb_base.png"
    br.screenshot(base, wid)

    # Coba tekan di tengah pill, lalu di ikon (x lebih kiri)
    for label, tx in (("tengah pill", bx), ("ikon bulat", bx - 150)):
        print(f"\n=== tekan di {label} ({tx},{by}) ===")
        # Masuk ke tombol dengan hover dulu (PX butuh pointer benar-benar masuk)
        hand.move_instant(tx - 120, by - 60)
        time.sleep(0.25)
        hand.move_to(tx, by, duration=0.45)
        time.sleep(0.5)
        hover = f"/tmp/_hb_hover_{tx}.png"
        br.screenshot(hover, wid)
        print(f"  diff setelah hover : {shot_diff(base, hover)}")

        hand.press()
        for dt in (0.5, 2.0, 4.0):
            time.sleep(dt if dt == 0.5 else dt - 0.5)
            f = f"/tmp/_hb_hold_{tx}_{dt}.png"
            br.screenshot(f, wid)
            print(f"  diff saat hold {dt}s: {shot_diff(base, f)}")
        hand.release()
        # Tunggu lebih lama: kalau PX sedang memproses di sisi server, vonisnya bisa
        # datang belakangan. Cetak SEMUA pesan yang challenge kirim ke wrapper.
        for dt in (1.0, 5.0, 10.0, 15.0):
            time.sleep(dt if dt == 1.0 else dt - 1.0 if dt == 5.0 else 5.0)
            f = f"/tmp/_hb_rel_{tx}_{dt}.png"
            br.screenshot(f, wid)
            print(f"  diff setelah lepas {dt}s: {shot_diff(base, f)}")
        print(f"\n  --- semua pesan wrapper ({len(wrap.events)}) ---")
        for e in wrap.events[-14:]:
            d = e.get("data")
            if isinstance(d, dict) and d.get("type") == "cookie":
                print(f"    cookie {d.get('name')} len={len(str(d.get('value') or ''))}")
            else:
                print(f"    {json.dumps(e)[:180]}")
        base = f"/tmp/_hb_rel_{tx}_15.0.png"
finally:
    br.stop()
    wrap.close()
    subprocess.run(["rm", "-rf", profile], check=False)
