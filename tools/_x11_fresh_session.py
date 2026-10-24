#!/usr/bin/env python3
"""Sesi bersih: launch browser (tanpa proxy) -> walk signup -> gate segar -> hold -> pantau.

Kenapa tanpa proxy: dengan proxy HP Microsoft langsung "Account creation has been
blocked" (pool sudah terbakar 337 akun); lewat IP VPS gate PX justru muncul.

Pantauan hold: bandingkan state tombol dengan baseline sesi INI (bukan sesi lama),
supaya "Please try again" sisa percobaan lama tidak salah dibaca sebagai penolakan.
"""
import hashlib
import os
import random
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11fresh"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11fresh_profile"
URL = "https://signup.live.com/signup?lic=1"


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def region_hash(tag, geom="300x90+500+645"):
    """Hash region tombol+strip error, untuk mendeteksi perubahan state."""
    src = f"{SHOTS}/{tag}.png"
    p = f"/tmp/_rh.png"
    r = subprocess.run(["convert", src, "-crop", geom, "+repage", p],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "ERR"
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


# ---------- 1. launch browser tanpa proxy ----------
subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
time.sleep(2)
subprocess.run(["rm", "-rf", PROFILE], check=False)
os.makedirs(PROFILE, exist_ok=True)
subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  "--fingerprint=424242", "--fingerprint-platform=windows",
                  "--window-size=1280,900", "--window-position=0,0",
                  "--no-first-run", "--no-default-browser-check", URL],
                 stdout=open("/tmp/x11fresh.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})
print("browser dijalankan, tunggu 16s")
time.sleep(16)


def find_wid():
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if not m:
            continue
        a = int(m.group(1)) * int(m.group(2))
        if a > a0:
            best, a0 = w, a
    return best


WID = find_wid()
print("WID:", WID, "|", run("xdotool", "getwindowname", WID))


def title():
    return run("xdotool", "getwindowname", WID)


def click_at(x, y):
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = x, y
    for i in range(1, 15):
        t = i / 14; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (x - sx) * e)), str(int(sy + (y - sy) * e)))
        time.sleep(random.uniform(0.01, 0.025))
    xdo("mousemove", str(x), str(y)); time.sleep(0.25)
    xdo("click", "1"); time.sleep(0.6)


def read_field():
    xdo("key", "ctrl+a"); time.sleep(0.3)
    xdo("key", "ctrl+c"); time.sleep(0.4)
    return subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                          capture_output=True, text=True).stdout.strip()


def type_verified(x, y, s, label):
    click_at(x, y)
    xdo("type", "--delay", "60", s)
    time.sleep(0.5)
    got = read_field()
    print(f"  [{label}] readback={got[:45]!r} ok={got == s}")
    return got == s


# ---------- 2. walk ----------
xdo("windowactivate", WID); time.sleep(0.8)
xdo("key", "ctrl+l"); time.sleep(0.6)
xdo("type", "--delay", "25", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(11)
print("form:", title()); shot("F0_form")

email = f"x11f{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
print("email:", email)

type_verified(638, 498, email, "email"); shot("F1_email")
click_at(638, 574); time.sleep(7); print("after email:", title()); shot("F2_pw")
type_verified(638, 535, pw, "password"); shot("F3_pw")
click_at(638, 645); time.sleep(7); print("after pw:", title()); shot("F4_details")

click_at(516, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
click_at(639, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
type_verified(760, 536, str(random.randint(1988, 2000)), "year"); shot("F5_birthdate")
click_at(640, 710); time.sleep(7); print("after birthdate:", title()); shot("F6_name")

type_verified(650, 432, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]), "first")
type_verified(650, 512, random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]), "last")
shot("F7_name")
click_at(650, 722); time.sleep(12)
t = title(); print("after submit:", t); shot("F8_submit")
if "prove" not in t.lower():
    time.sleep(10); t = title(); print("lagi:", t); shot("F9_wait")
if "prove" not in t.lower():
    print(">>> gate TIDAK muncul:", t)
    sys.exit(2)

# ---------- 3. gate segar: baseline dulu ----------
print(">>> GATE SEGAR")
time.sleep(2); shot("G0_fresh_gate")
base = region_hash("G0_fresh_gate")
print("baseline region hash:", base)

# ---------- 4. hold dengan biomekanik ----------
BX, BY = 660, 689
out = run("xdotool", "getmouselocation")
sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
for i in range(1, 23):
    t = i / 22; e = 1 - (1 - t) ** 2.2
    xdo("mousemove", str(int(sx + (BX - sx) * e + random.uniform(-1.0, 1.0))),
        str(int(sy + (BY - sy) * e + random.uniform(-1.0, 1.0))))
    time.sleep(random.uniform(0.012, 0.03))
xdo("mousemove", str(BX), str(BY)); time.sleep(0.4)
xdo("mousemove", str(BX + random.randint(-2, 2)), str(BY - random.randint(2, 5)))
time.sleep(random.uniform(0.06, 0.13))
xdo("mousemove", str(BX), str(BY)); time.sleep(0.08)
xdo("mousedown", "1")
print("  mousedown — pantau 20s")
t0, cx, cy, i = time.time(), float(BX), float(BY), 0
while time.time() - t0 < 20:
    cx = min(max(cx + random.uniform(-1.3, 1.3), BX - 18), BX + 18)
    cy = min(max(cy + random.uniform(-0.9, 0.9), BY - 5), BY + 5)
    xdo("mousemove", str(int(cx)), str(int(cy)))
    i += 1
    time.sleep(random.uniform(0.03, 0.14) if random.random() > 0.15
               else random.uniform(0.2, 0.45))
    el = time.time() - t0
    if i % 25 == 0:
        tag = f"G_hold_{int(el):02d}s"
        shot(tag)
        h = region_hash(tag)
        print(f"  t={el:4.1f}s hash={h} {'' if h == base else '<-- BERUBAH dari baseline'}")
xdo("mouseup", "1")
print(f"  mouseup setelah {time.time()-t0:.1f}s")
time.sleep(3); shot("G_released"); print("after hold:", title())
time.sleep(5); shot("G_after5"); print("+5s:", title())
time.sleep(10); shot("G_final"); print("final:", title())
