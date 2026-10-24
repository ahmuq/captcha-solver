#!/usr/bin/env python3
"""Satu sesi: walk -> gate segar -> 3 variasi hold, rekam tiap 1.2s.

Tujuan: tahu KAPAN PX menolak (saat masih ditahan, atau setelah dilepas) dan apakah
variasi gesture mengubah hasil. Screenshot berkala supaya penilaiannya berbasis bukti,
bukan tebakan.
"""
import hashlib
import os
import random
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11var"
os.makedirs(SHOTS, exist_ok=True)
BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = "/tmp/x11var_profile"
URL = "https://signup.live.com/signup?lic=1"
BX, BY = 660, 689


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------- launch ----------
subprocess.run(["pkill", "-f", "user-data-dir=/tmp/x11"], check=False)
time.sleep(2)
subprocess.run(["rm", "-rf", PROFILE], check=False)
os.makedirs(PROFILE, exist_ok=True)
subprocess.Popen([BIN, f"--user-data-dir={PROFILE}", "--no-sandbox",
                  "--fingerprint=424242", "--fingerprint-platform=windows",
                  "--window-size=1280,900", "--window-position=0,0",
                  "--no-first-run", "--no-default-browser-check", URL],
                 stdout=open("/tmp/x11var.log", "w"), stderr=subprocess.STDOUT,
                 env={**os.environ, "DISPLAY": ":99"})
print("launch, tunggu 16s")
time.sleep(16)


def find_wid():
    best, a0 = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if m and int(m.group(1)) * int(m.group(2)) > a0:
            best, a0 = w, int(m.group(1)) * int(m.group(2))
    return best


WID = find_wid()
print("WID:", WID, "|", run("xdotool", "getwindowname", WID))


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def rhash(tag, geom="320x95+490+640"):
    p = "/tmp/_rv.png"
    r = subprocess.run(["convert", f"{SHOTS}/{tag}.png", "-crop", geom, "+repage", p],
                       capture_output=True, text=True)
    if r.returncode:
        return "ERR"
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:8]


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
    print(f"  [{label}] ok={got == s} readback={got[:40]!r}")


# ---------- walk ----------
xdo("windowactivate", WID); time.sleep(0.8)
xdo("key", "ctrl+l"); time.sleep(0.6)
xdo("type", "--delay", "25", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(11)
print("form:", title())

email = f"x11z{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
print("email:", email)

type_verified(638, 498, email, "email")
click_at(638, 574); time.sleep(7); print("after email:", title())
type_verified(638, 535, pw, "password")
click_at(638, 645); time.sleep(7); print("after pw:", title())

click_at(516, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
click_at(639, 536); time.sleep(1.2)
xdo("key", "Down"); time.sleep(0.4); xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
type_verified(760, 536, str(random.randint(1988, 2000)), "year")
click_at(640, 710); time.sleep(7); print("after birthdate:", title())

type_verified(650, 432, random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]), "first")
type_verified(650, 512, random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]), "last")
click_at(650, 722); time.sleep(12)
t = title(); print("after submit:", t)
if "prove" not in t.lower():
    time.sleep(10); t = title(); print("lagi:", t)
if "prove" not in t.lower():
    print(">>> gate TIDAK muncul:", t); sys.exit(2)

print(">>> GATE SEGAR")
time.sleep(2)
shot("V0_baseline")
base = rhash("V0_baseline")
print("baseline hash:", base)


def approach():
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = BX, BY
    for i in range(1, 24):
        t = i / 23; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (BX - sx) * e + random.uniform(-1.0, 1.0))),
            str(int(sy + (BY - sy) * e + random.uniform(-1.0, 1.0))))
        time.sleep(random.uniform(0.012, 0.03))
    xdo("mousemove", str(BX), str(BY)); time.sleep(random.uniform(0.4, 0.8))


def do_hold(name, seconds, amp, rate_lo, rate_hi, pause_prob=0.0):
    """Tahan tombol sambil merekam tiap 1.2s."""
    print(f"\n=== {name}: hold {seconds}s amp={amp} rate={rate_lo}-{rate_hi} ===")
    approach()
    xdo("mousedown", "1")
    t0, cx, cy, i, last_shot = time.time(), float(BX), float(BY), 0, 0.0
    shot(f"{name}_00s")
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-amp, amp), BX - 22), BX + 22)
        cy = min(max(cy + random.uniform(-amp, amp), BY - 6), BY + 6)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        i += 1
        time.sleep(random.uniform(rate_lo, rate_hi) if random.random() > pause_prob
                   else random.uniform(0.25, 0.6))
        el = time.time() - t0
        if el - last_shot >= 1.2:
            tag = f"{name}_{int(el):02d}s"
            shot(tag)
            h = rhash(tag)
            print(f"  t={el:4.1f}s hash={h}{'' if h == base else ' <-BERUBAH'}")
            last_shot = el
    xdo("mouseup", "1")
    print(f"  mouseup setelah {time.time()-t0:.1f}s")
    time.sleep(2)
    shot(f"{name}_rel")
    print(f"  judul: {title()!r}")
    return "prove" not in title().lower()


# Variasi 1: tremor halus & jarang (paling menyerupai tangan diam)
if do_hold("A", 8, 1.0, 0.18, 0.5, pause_prob=0.25):
    print(">>> LOLOS pada variasi A"); sys.exit(0)

time.sleep(3)
shot("A_retry_base")

# Variasi 2: gerak lebih hidup
if do_hold("B", 7, 3.0, 0.08, 0.22):
    print(">>> LOLOS pada variasi B"); sys.exit(0)

time.sleep(3)

# Variasi 3: tahan lama, gerak sangat jarang (hampir diam total)
if do_hold("C", 14, 0.6, 0.35, 0.9, pause_prob=0.4):
    print(">>> LOLOS pada variasi C"); sys.exit(0)

time.sleep(4)
shot("C_final")
print("final:", title())
print("SEMUA VARIASI DITOLAK")
