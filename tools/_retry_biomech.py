#!/usr/bin/env python3
"""Retry berjeda: tunggu throttle Microsoft mereda, lalu uji hand 100 Hz di gate segar.

Blocker saat ini: semua IP (VPS + 3 prefix HP) diblokir "Account creation has been
blocked". Loop ini mencoba tiap ~20 menit, dan HANYA saat gate PX muncul ia menjalankan
press & hold dengan tangan biomekanik 100 Hz (yang belum pernah teruji di gate segar).
Hasil ditulis ke /tmp/px_retry.log.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from _hloop_walk import walk, hold

LOG = "/tmp/px_retry.log"
ROUNDS = int(os.environ.get("ROUNDS", "6"))
WAIT = float(os.environ.get("WAIT", "1200"))
USE_PROXY = os.environ.get("USE_PROXY", "1") == "1"


def note(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    _hloop.log(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def launch():
    if USE_PROXY:
        return _hloop.launch()
    import re, subprocess
    BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
    P = "/tmp/x11retry_profile"
    subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
    time.sleep(2.5)
    subprocess.run(["rm", "-rf", P], check=False)
    os.makedirs(P, exist_ok=True)
    subprocess.Popen([BIN, f"--user-data-dir={P}", "--no-sandbox",
                      "--fingerprint=424242", "--fingerprint-platform=windows",
                      "--window-size=1280,900", "--window-position=0,0",
                      "--no-first-run", "--no-default-browser-check",
                      "https://signup.live.com/signup?lic=1"],
                     stdout=open("/tmp/x11retry.log", "w"), stderr=subprocess.STDOUT,
                     env={**os.environ, "DISPLAY": ":99"})
    time.sleep(18)
    best, a0 = None, 0
    for w in _hloop.run("xdotool", "search", "--name", "").splitlines():
        t = _hloop.run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)",
                      _hloop.run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best


note(f"retry dimulai: {ROUNDS} putaran, jeda {WAIT:.0f}s, proxy={USE_PROXY}")
for i in range(1, ROUNDS + 1):
    note(f"--- putaran {i}/{ROUNDS} ---")
    if USE_PROXY:
        ip = _hloop.rotate()
        note(f"IP: {ip}")
    WID = launch()
    if not WID:
        note("window tidak ketemu"); time.sleep(60); continue
    t = walk(WID, f"r{i}")
    note(f"submit: {t}")
    if "prove" in t.lower():
        note(">>> GATE MUNCUL — uji hand 100 Hz")
        t = hold(WID, f"r{i}")
        if "prove" not in t.lower():
            note(f">>> LOLOS! halaman maju: {t}")
            sys.exit(0)
        note("masih di gate setelah hold 100 Hz")
    else:
        note("tidak ada gate (masih throttle)")
    if i < ROUNDS:
        note(f"tunggu {WAIT:.0f}s")
        time.sleep(WAIT)

note("retry selesai tanpa lolos")
