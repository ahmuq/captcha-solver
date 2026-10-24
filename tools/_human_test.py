#!/usr/bin/env python3
"""Uji pola email gaya manusia di @outlook.com, dengan verifikasi tiap step.

Temuan sebelumnya: pola mesin `x11L######@outlook.com` SELALU diblokir, sedangkan
pola manusia (`fajar.santoso36@...`) tidak. Uji ini memakai alias gaya manusia dengan
entropi lebih besar, memverifikasi step benar-benar maju, dan mencoba alias baru kalau
Microsoft menolak (mis. alias sudah dipakai).
"""
import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from px_hand import Hand
from _hloop_walk import hold
from _hloop_walk import key, typ, S, T

FIRST = ["nathan", "bagas", "rendy", "fajar", "dinda", "sari", "arif", "dewi",
         "putra", "ratna", "yoga", "maya", "dimas", "intan", "rizky", "wulan"]
LAST = ["kusuma", "pratama", "santoso", "wijaya", "lestari", "hidayat", "nugroho",
        "permata", "saputra", "maulana", "firdaus", "anggraini"]


def note(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    _hloop.log(line)
    with open("/tmp/px_human.log", "a") as f:
        f.write(line + "\n")


def human_alias() -> str:
    """Gaya manusia: nama+nama+angka, kadang pakai titik, panjang bervariasi."""
    f, l = random.choice(FIRST), random.choice(LAST)
    sep = random.choice(["", ".", "_"])
    num = str(random.randint(1000, 99999)) if random.random() < 0.6 else ""
    return f"{f}{sep}{l}{num}"


def fill_step(WID, hand, x, y, value, label):
    hand.click(x, y)
    typ(WID, value)
    time.sleep(0.4)
    return T(WID)


def try_alias(WID, tag, email):
    """Isi form; kembalikan (judul_akhir, maju?) dengan cek step per langkah."""
    hand = Hand(":99")
    key(WID, "ctrl+l", 0.6)
    typ(WID, "https://signup.live.com/signup?lic=1")
    key(WID, "Return", 12)
    t0 = T(WID)
    note(f"[{tag}] form: {t0}")
    S(WID, f"{tag}_form")
    if "Create your Microsoft account" not in t0:
        return t0, False

    note(f"[{tag}] email: {email}")
    hand.click(638, 498); typ(WID, email); S(WID, f"{tag}_email")
    hand.click(638, 574); time.sleep(7)
    t1 = T(WID)
    note(f"[{tag}] step2: {t1}")
    S(WID, f"{tag}_step2")
    if "password" not in t1.lower():
        # alias ditolak (mis. sudah dipakai) atau Next meleset
        return t1, False

    hand.click(638, 535); typ(WID, "Zx9kLmQ2vRt7pW!4"); S(WID, f"{tag}_pw")
    hand.click(638, 645); time.sleep(7)
    t2 = T(WID)
    note(f"[{tag}] step3: {t2}")
    S(WID, f"{tag}_step3")
    if "details" not in t2.lower():
        return t2, False

    for _, (dx, dy) in [("m", (516, 536)), ("d", (639, 536))]:
        hand.click(dx, dy); time.sleep(1.1)
        key(WID, "Down", 0.35); key(WID, "Down", 0.35); key(WID, "Return", 1.1)
    hand.click(760, 536); typ(WID, str(random.randint(1988, 2000)))
    hand.click(640, 710); time.sleep(7)
    t3 = T(WID)
    note(f"[{tag}] step4: {t3}")
    S(WID, f"{tag}_step4")
    if "name" not in t3.lower():
        return t3, False

    hand.click(650, 432); typ(WID, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
    hand.click(650, 512); typ(WID, random.choice(["Kusumo", "Pratama", "Wijaya"]))
    hand.click(650, 722); time.sleep(12)
    t4 = T(WID)
    note(f"[{tag}] submit: {t4}")
    S(WID, f"{tag}_submit")
    if "prove" not in t4.lower():
        time.sleep(10); t4 = T(WID); note(f"[{tag}] lagi: {t4}")
    return t4, True


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


N = int(os.environ.get("N", "3"))
note(f"uji alias manusia @outlook.com: {N} sesi")
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
    email = human_alias() + "@outlook.com"
    t, advanced = try_alias(WID, f"h{i}", email)
    note(f"[h{i}] advanced={advanced} hasil={t}")
    if "prove" in t.lower():
        note(f">>> GATE MUNCUL dengan {email} — hold biomekanik")
        t = hold(WID, f"h{i}")
        if "prove" not in t.lower():
            note(f">>> LOLOS: {t}")
            sys.exit(0)
        note(f"masih di gate: {t}")
    time.sleep(20)

note("selesai")
