#!/usr/bin/env python3
"""Bagian walk + hold untuk _hloop (dipisah agar file tetap kecil)."""
import os, random, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from px_hand import Hand
from _hloop import log, run, SHOTS, BX, BY


def key(WID, k, w=0.6):
    subprocess.run(["xdotool", "key", "--window", WID, k], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(w)


def typ(WID, s):
    subprocess.run(["xdotool", "type", "--window", WID, "--delay", "55", s], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.5)


def S(WID, n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def T(WID):
    return run("xdotool", "getwindowname", WID)


def walk(WID, tag):
    """Isi form sampai submit. Mengembalikan judul setelah submit."""
    hand = Hand(":99")
    subprocess.run(["xdotool", "windowactivate", WID], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    key(WID, "ctrl+l", 0.6)
    typ(WID, "https://signup.live.com/signup?lic=1")
    key(WID, "Return", 12)
    log(f"[{tag}] form: {T(WID)}")
    S(WID, f"{tag}_form")

    email = f"x11L{random.randint(100000,999999)}@outlook.com"
    pw = "Zx9kLmQ2vRt7pW!4"
    log(f"[{tag}] email: {email}")

    hand.click(638, 498); typ(WID, email); S(WID, f"{tag}_email")
    hand.click(638, 574); time.sleep(7); log(f"[{tag}] +email: {T(WID)}")
    hand.click(638, 535); typ(WID, pw); S(WID, f"{tag}_pw")
    hand.click(638, 645); time.sleep(7); log(f"[{tag}] +pw: {T(WID)}")
    for _, (dx, dy) in [("m", (516, 536)), ("d", (639, 536))]:
        hand.click(dx, dy); time.sleep(1.1)
        key(WID, "Down", 0.35); key(WID, "Down", 0.35); key(WID, "Return", 1.1)
    hand.click(760, 536); typ(WID, str(random.randint(1988, 2000)))
    hand.click(640, 710); time.sleep(7); log(f"[{tag}] +birth: {T(WID)}")
    S(WID, f"{tag}_details")
    hand.click(650, 432); typ(WID, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
    hand.click(650, 512); typ(WID, random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]))
    hand.click(650, 722); time.sleep(12)
    t = T(WID)
    log(f"[{tag}] after submit: {t}")
    S(WID, f"{tag}_submit")
    if "prove" not in t.lower():
        time.sleep(10); t = T(WID); log(f"[{tag}] lagi: {t}"); S(WID, f"{tag}_wait")
    return t


def hold(WID, tag):
    log(f"[{tag}] >>> GATE — press & hold biomekanik")
    hand = Hand(":99")
    time.sleep(1.5); S(WID, f"{tag}_gate")
    hand.press_and_hold(seconds=9.0, x=BX, y=BY, log=lambda m: log(f"[{tag}]{m}"))
    time.sleep(2.5); S(WID, f"{tag}_released")
    log(f"[{tag}] setelah lepas: {T(WID)}")
    time.sleep(5); log(f"[{tag}] +5s: {T(WID)}")
    time.sleep(10)
    t = T(WID); S(WID, f"{tag}_final"); log(f"[{tag}] final: {t}")

    # Panen SEGERA: _px3 hanya hidup ~10 menit, dan panen butuh profil ditutup
    # dengan rapi (SIGTERM) supaya store-nya ditulis ke disk.
    try:
        from px_harvest import harvest, cookie_header
        import os as _os
        prof = _os.environ.get("PROFILE", "/tmp/x11lp_profile")
        res = harvest(prof)
        if res.get("error"):
            log(f"[{tag}] panen gagal: {res['error']}")
        else:
            c = res.get("cookies", {})
            log(f"[{tag}] panen: {sorted(c)} (dari {res.get('total')} cookie)")
            for n in sorted(c):
                log(f"[{tag}]   {n:8} len={len(c[n])}")
            if c:
                log(f"[{tag}] header {len(cookie_header(c))} byte -> /tmp/px_cookies.json")
    except Exception as e:
        log(f"[{tag}] panen error: {e}")
    return t
