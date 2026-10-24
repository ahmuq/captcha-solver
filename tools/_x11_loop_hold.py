#!/usr/bin/env python3
"""Loop sesi sampai gate PX muncul, lalu press & hold dengan tangan biomekanik.

Microsoft bersifat intermiten: sebagian sesi langsung "Account creation has been
blocked" (tanpa gate), sebagian menampilkan gate PX. Skrip ini mengulang sesi baru
(profil + email baru) sampai gate muncul, lalu mengerjakan hold-nya.
"""
import os
import random
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from px_hand import Hand

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11loop"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11loop_profile"
URL = "https://signup.live.com/signup?lic=1"
BX, BY = 660, 689
MAX_ATTEMPTS = int(os.environ.get("MAX_ATTEMPTS", "4"))


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def log(m):
    print(m, flush=True)


def key(k, wait=0.6, wid=None):
    subprocess.run(["xdotool", "key", "--window", wid, k], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)


def typ(s, wid=None):
    subprocess.run(["xdotool", "type", "--window", wid, "--delay", "55", s],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


def launch(tag):
    subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
    time.sleep(2.5)
    subprocess.run(["rm", "-rf", PROFILE], check=False)
    os.makedirs(PROFILE, exist_ok=True)
    subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                      "--fingerprint=424242", "--fingerprint-platform=windows",
                      "--window-size=1280,900", "--window-position=0,0",
                      "--no-first-run", "--no-default-browser-check", URL],
                     stdout=open(f"/tmp/x11loop_{tag}.log", "w"),
                     stderr=subprocess.STDOUT, env={**os.environ, "DISPLAY": ":99"})
    time.sleep(17)
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best


def one_attempt(n):
    tag = f"a{n}"
    WID = launch(tag)
    if not WID:
        log(f"[{tag}] window tidak ketemu"); return None, None

    def T():
        return run("xdotool", "getwindowname", WID)

    def S(nm):
        subprocess.run(["import", "-window", WID, f"{SHOTS}/{tag}_{nm}.png"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    hand = Hand(":99")
    subprocess.run(["xdotool", "windowactivate", WID], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    key("ctrl+l", 0.6, WID)
    typ(URL, WID)
    key("Return", 11, WID)
    log(f"[{tag}] form: {T()}")

    email = f"x11n{random.randint(100000,999999)}@outlook.com"
    pw = "Zx9kLmQ2vRt7pW!4"
    log(f"[{tag}] email: {email}")

    hand.click(638, 498); typ(email, WID); S("email")
    hand.click(638, 574); time.sleep(7); log(f"[{tag}] after email: {T()}")
    hand.click(638, 535); typ(pw, WID); S("pw")
    hand.click(638, 645); time.sleep(7); log(f"[{tag}] after pw: {T()}")

    for label, (dx, dy) in [("month", (516, 536)), ("day", (639, 536))]:
        hand.click(dx, dy); time.sleep(1.1)
        key("Down", 0.35, WID); key("Down", 0.35, WID); key("Return", 1.1, WID)
    hand.click(760, 536); typ(str(random.randint(1988, 2000)), WID)
    hand.click(640, 710); time.sleep(7); log(f"[{tag}] after birthdate: {T()}")
    S("details")

    hand.click(650, 432); typ(random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]), WID)
    hand.click(650, 512); typ(random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]), WID)
    hand.click(650, 722); time.sleep(12)
    t = T()
    log(f"[{tag}] after submit: {t}")
    S("submit")
    if "prove" not in t.lower():
        time.sleep(10); t = T(); log(f"[{tag}] lagi: {t}"); S("wait")
    return WID, t


for n in range(1, MAX_ATTEMPTS + 1):
    log(f"\n========== PERCOBAAN {n}/{MAX_ATTEMPTS} ==========")
    WID, t = one_attempt(n)
    if not WID:
        continue
    if "prove" not in (t or "").lower():
        log(f"[a{n}] tidak ada gate ({t}) — ulangi sesi baru")
        continue

    # gate muncul -> hold biomekanik
    log(f"[a{n}] >>> GATE MUNCUL — press & hold biomekanik")
    hand = Hand(":99")
    time.sleep(1.5)
    subprocess.run(["import", "-window", WID, f"{SHOTS}/a{n}_gate.png"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    held = hand.press_and_hold(seconds=9.0, x=BX, y=BY, log=lambda m: log(f"[a{n}]{m}"))
    time.sleep(2.5)
    subprocess.run(["import", "-window", WID, f"{SHOTS}/a{n}_released.png"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t = run("xdotool", "getwindowname", WID)
    log(f"[a{n}] setelah lepas: {t}")
    time.sleep(5)
    log(f"[a{n}] +5s: {run('xdotool', 'getwindowname', WID)}")
    time.sleep(10)
    t = run("xdotool", "getwindowname", WID)
    log(f"[a{n}] final: {t}")
    subprocess.run(["import", "-window", WID, f"{SHOTS}/a{n}_final.png"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        subprocess.run(["cp", f"{PROFILE}/Default/Cookies", "/tmp/_loop_ck.db"], check=True)
        c = sqlite3.connect("/tmp/_loop_ck.db")
        px = [(r[0], r[2]) for r in c.execute(
            "select name,host_key,length(encrypted_value) from cookies").fetchall()
            if r[0].startswith("_px") or r[0] == "pxcts"]
        log(f"[a{n}] cookie PX: {px}")
    except Exception as e:
        log(f"[a{n}] gagal baca cookie: {e}")

    if "prove" not in t.lower():
        log(f"[a{n}] >>> LOLOS: halaman maju dari gate ({t})")
        sys.exit(0)
    else:
        log(f"[a{n}] masih di gate — coba sesi baru")
        continue

log("\nsemua percobaan selesai tanpa lolos")
