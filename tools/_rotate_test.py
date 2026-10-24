#!/usr/bin/env python3
"""Tes berotasi lewat proxy HP: tiap sesi rotate IP baru, walk X11, hold biomekanik.

Alur per sesi:
  rotate -> tunggu egress berganti (radio butuh ~10-15s) -> launch X11 lewat proxy
  -> walk signup -> kalau gate muncul: press & hold tangan 100 Hz -> panen cookie.
Setiap sesi memakai profil baru supaya gate selalu segar (verdict lama menempel).
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from _hloop_walk import walk, hold

ROUNDS = int(os.environ.get("ROUNDS", "3"))
WAIT = float(os.environ.get("WAIT", "45"))


def note(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    _hloop.log(line)
    with open("/tmp/px_rotate.log", "a") as f:
        f.write(line + "\n")


def rotate_until_new(old=""):
    """Rotate, lalu poll egress sampai berubah dan proxy benar-benar melayani."""
    _hloop.run("curl", "-s", "--max-time", "40",
               "http://178.83.181.16:18081/rotate?token=capok123")
    ip = ""
    for i in range(14):
        time.sleep(7)
        ip = _hloop.run("curl", "-s", "--max-time", "25", "-x", _hloop.PROXY,
                        "https://api.ipify.org")
        if ip and ip != old:
            # pastikan jalur ke target hidup, bukan cuma ipify
            code = _hloop.run("curl", "-s", "--max-time", "30", "-o", "/dev/null",
                              "-w", "%{http_code}", "-x", _hloop.PROXY,
                              "https://signup.live.com/signup?lic=1")
            note(f"  poll {i+1}: ip={ip or 'kosong'} target={code}")
            if code == "200":
                return ip
        else:
            note(f"  poll {i+1}: ip={ip or 'kosong'} (belum berganti)")
    return ip


note(f"tes berotasi dimulai: {ROUNDS} sesi, jeda {WAIT:.0f}s")
for i in range(1, ROUNDS + 1):
    note(f"===== SESI {i}/{ROUNDS} =====")
    ip = rotate_until_new()
    if not ip:
        # Proxy HP sedang cycling (klien FRP di HP flap) -> coba sekali lagi,
        # kalau tetap mati lewati sesi. Membuka browser saat proxy mati hanya
        # menghasilkan ERR_PROXY_CONNECTION_FAILED yang tak informatif.
        note("IP gagal didapat — coba rotasi ulang sekali")
        time.sleep(20)
        ip = rotate_until_new()
    if not ip:
        note("proxy masih mati — lewati sesi ini")
        continue
    note(f"IP sesi ini: {ip}")
    time.sleep(WAIT)          # beri waktu radio proxy stabil sebelum browser buka
    WID = _hloop.launch()
    if not WID:
        note("window tidak ketemu"); continue
    note(f"WID={WID}")
    t = walk(WID, f"r{i}")
    note(f"submit: {t}")
    if "prove" in t.lower():
        note(">>> GATE MUNCUL — hold biomekanik + panen")
        t = hold(WID, f"r{i}")
        if "prove" not in t.lower():
            note(f">>> LOLOS! {t}")
            sys.exit(0)
        note(f"masih di gate: {t}")
    else:
        note(f"tidak ada gate: {t}")
    if i < ROUNDS:
        note(f"jeda {WAIT:.0f}s")
        time.sleep(WAIT)

note("selesai tanpa lolos")
