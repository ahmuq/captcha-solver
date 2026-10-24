#!/usr/bin/env python3
"""Uji variabel domain email: pola email mesin vs domain lain.

Semua uji sebelumnya memakai pola `x11L123456@outlook.com` (huruf + 6 digit,
selalu sama). Risk engine Microsoft mudah menandai pola seperti itu. Uji ini
membandingkan domain @outlook.com vs domain recovery yang kita punya
(bagahmail.com) dalam sesi terpisah, dengan rotasi IP HP tiap sesi.
"""
import os, random, string, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from px_hand import Hand
from _hloop_walk import walk as _walk, hold
from _hloop_walk import key, typ, S, T


def note(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    _hloop.log(line)
    with open("/tmp/px_domain.log", "a") as f:
        f.write(line + "\n")


def rand_user(style: str) -> str:
    if style == "machine":
        return f"x11L{random.randint(100000, 999999)}"
    # gaya manusia: nama + angka pendek
    first = random.choice(["nathan", "bagas", "rendy", "fajar", "dinda", "sari"])
    last = random.choice(["kusuma", "pratama", "santoso", "wijaya", "lestari"])
    return f"{first}.{last}{random.randint(10, 99)}"


def walk_with_email(WID, tag, email):
    hand = Hand(":99")
    key(WID, "ctrl+l", 0.6)
    typ(WID, "https://signup.live.com/signup?lic=1")
    key(WID, "Return", 12)
    note(f"[{tag}] form: {T(WID)}")
    S(WID, f"{tag}_form")
    note(f"[{tag}] email: {email}")
    hand.click(638, 498); typ(WID, email); S(WID, f"{tag}_email")
    hand.click(638, 574); time.sleep(7); note(f"[{tag}] +email: {T(WID)}")
    hand.click(638, 535); typ(WID, "Zx9kLmQ2vRt7pW!4"); S(WID, f"{tag}_pw")
    hand.click(638, 645); time.sleep(7); note(f"[{tag}] +pw: {T(WID)}")
    for _, (dx, dy) in [("m", (516, 536)), ("d", (639, 536))]:
        hand.click(dx, dy); time.sleep(1.1)
        key(WID, "Down", 0.35); key(WID, "Down", 0.35); key(WID, "Return", 1.1)
    hand.click(760, 536); typ(WID, str(random.randint(1988, 2000)))
    hand.click(640, 710); time.sleep(7); note(f"[{tag}] +birth: {T(WID)}")
    S(WID, f"{tag}_details")
    hand.click(650, 432); typ(WID, random.choice(["Nathan", "Bagas", "Rendy"]))
    hand.click(650, 512); typ(WID, random.choice(["Kusumo", "Pratama", "Wijaya"]))
    hand.click(650, 722); time.sleep(12)
    t = T(WID); note(f"[{tag}] after submit: {t}"); S(WID, f"{tag}_submit")
    if "prove" not in t.lower():
        time.sleep(10); t = T(WID); note(f"[{tag}] lagi: {t}"); S(WID, f"{tag}_wait")
    return t


def rotate():
    _hloop.run("curl", "-s", "--max-time", "40",
               "http://178.83.181.16:18081/rotate?token=capok123")
    for _ in range(14):
        time.sleep(7)
        ip = _hloop.run("curl", "-s", "--max-time", "25", "-x", _hloop.PROXY,
                        "https://api.ipify.org")
        if ip:
            code = _hloop.run("curl", "-s", "--max-time", "30", "-o", "/dev/null",
                              "-w", "%{http_code}", "-x", _hloop.PROXY,
                              "https://signup.live.com/signup?lic=1")
            if code == "200":
                return ip
    return ""


CASES = [
    ("machine_outlook", lambda: rand_user("machine") + "@outlook.com"),
    ("human_bagah", lambda: rand_user("human") + "@bagahmail.com"),
    ("human_outlook", lambda: rand_user("human") + "@outlook.com"),
]

note(f"uji domain dimulai: {len(CASES)} kasus")
for name, mk in CASES:
    note(f"===== {name} =====")
    ip = rotate()
    if not ip:
        note("proxy mati — lewati"); continue
    note(f"IP: {ip}")
    time.sleep(45)
    WID = _hloop.launch()
    if not WID:
        note("window tidak ketemu"); continue
    email = mk()
    t = walk_with_email(WID, name, email)
    if "prove" in t.lower():
        note(f">>> GATE MUNCUL pada {name} — hold biomekanik")
        t = hold(WID, name)
        if "prove" not in t.lower():
            note(f">>> LOLOS pada {name}: {t}")
            sys.exit(0)
    note(f"{name}: {t}")
    time.sleep(30)

note("uji domain selesai")
