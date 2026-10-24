#!/usr/bin/env python3
"""Uji pola yang TERBUKTI menghasilkan 337 akun: `first.last###@outlook.co.id`.

Data akun bot (accounts/*.txt) semuanya berpola manusia di domain .co.id:
  nanda.purnomo222@outlook.co.id, arif.suharto7373@outlook.co.id, ...
sedangkan uji saya memakai `x11L######@outlook.com` (pola mesin) dan selalu diblokir.
Skrip ini menguji pola bot + domain .co.id, rotasi IP HP tiap sesi, dan kalau alias
sudah dipakai ia memakai saran dari Microsoft.
"""
import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from px_hand import Hand
from _hloop_walk import hold
from _hloop_walk import key, typ, S, T

FIRST = ["nanda", "arif", "mega", "gunawan", "ilham", "bayu", "susanto", "dedi",
         "lestari", "putri", "agus", "hendra", "ratna", "yudi", "sinta", "bambang"]
LAST = ["purnomo", "suharto", "susanto", "budi", "saputra", "permana", "firmansyah",
        "dewi", "wijaya", "setiawan", "hidayat", "nugroho", "maulana", "kurniawan"]
DOMAIN = os.environ.get("DOMAIN", "outlook.co.id")


def note(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    _hloop.log(line)
    with open("/tmp/px_coid.log", "a") as f:
        f.write(line + "\n")


def bot_alias() -> str:
    """Pola yang dipakai bot: first.last + 2-4 digit."""
    f, l = random.choice(FIRST), random.choice(LAST)
    n = random.randint(10, 9999)
    sep = "." if random.random() < 0.75 else ""
    return f"{f}{sep}{l}{n}"


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


def run_session(WID, tag, alias):
    """Isi form dengan alias; tangani 'username taken' dengan memakai saran MS."""
    hand = Hand(":99")
    key(WID, "ctrl+l", 0.6)
    typ(WID, "https://signup.live.com/signup?lic=1")
    key(WID, "Return", 12)
    t = T(WID)
    note(f"[{tag}] form: {t}")
    S(WID, f"{tag}_form")
    if "Create your Microsoft account" not in t:
        return t

    email = f"{alias}@{DOMAIN}"
    note(f"[{tag}] email: {email}")
    hand.click(638, 498); typ(WID, email); S(WID, f"{tag}_email")
    hand.click(638, 574); time.sleep(7)
    t = T(WID); S(WID, f"{tag}_step2")
    note(f"[{tag}] step2: {t}")
    if "password" not in t.lower():
        note(f"[{tag}] alias tidak diterima di step 2")
        return t

    hand.click(638, 535); typ(WID, "Zx9kLmQ2vRt7pW!4"); S(WID, f"{tag}_pw")
    hand.click(638, 645); time.sleep(7)
    t = T(WID); S(WID, f"{tag}_step3"); note(f"[{tag}] step3: {t}")
    if "details" not in t.lower():
        return t

    for _, (dx, dy) in [("m", (516, 536)), ("d", (639, 536))]:
        hand.click(dx, dy); time.sleep(1.1)
        key(WID, "Down", 0.35); key(WID, "Down", 0.35); key(WID, "Return", 1.1)
    hand.click(760, 536); typ(WID, str(random.randint(1988, 2000)))
    hand.click(640, 710); time.sleep(7)
    t = T(WID); S(WID, f"{tag}_step4"); note(f"[{tag}] step4: {t}")
    if "name" not in t.lower():
        return t

    hand.click(650, 432); typ(WID, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
    hand.click(650, 512); typ(WID, random.choice(["Kusumo", "Pratama", "Wijaya"]))
    hand.click(650, 722); time.sleep(12)
    t = T(WID); S(WID, f"{tag}_submit"); note(f"[{tag}] submit: {t}")
    if "prove" not in t.lower():
        time.sleep(10); t = T(WID); note(f"[{tag}] lagi: {t}"); S(WID, f"{tag}_wait")
    return t


N = int(os.environ.get("N", "3"))
note(f"uji pola bot @{DOMAIN}: {N} sesi")
for i in range(1, N + 1):
    note(f"===== SESI {i}/{N} =====")
    ip = rotate()
    if not ip:
        note("proxy mati — lewati"); continue
    note(f"IP: {ip}")
    time.sleep(45)
    WID = _hloop.launch()
    if not WID:
        note("window tidak ketemu"); continue
    alias = bot_alias()
    t = run_session(WID, f"c{i}", alias)
    if "prove" in t.lower():
        note(f">>> GATE MUNCUL ({alias}@{DOMAIN}) — hold biomekanik + panen")
        t = hold(WID, f"c{i}")
        if "prove" not in t.lower():
            note(f">>> LOLOS: {t}")
            sys.exit(0)
        note(f"masih di gate: {t}")
    time.sleep(20)

note("selesai")
