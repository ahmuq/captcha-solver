#!/usr/bin/env python3
"""Walker X11 berbasis KEYBOARD (Tab/Enter), bukan klik koordinat.

Alasan: layout Microsoft bergeser tiap step (field email y=498, password y=535,
details y=536, nama y=432/512), jadi koordinat hardcoded selalu meleset dan klik
jatuh ke link footer. Field-nya auto-focus saat step berganti, jadi mengetik langsung
+ Tab/Enter jauh lebih andal dan tidak butuh koordinat sama sekali.

Hanya dropdown Fluent (Month/Day) yang butuh interaksi khusus: fokus via Tab lalu
Down+Enter.
"""
import os
import random
import re
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
SHOTS = "/tmp/x11shots"
URL = "https://signup.live.com/signup?lic=1"
os.makedirs(SHOTS, exist_ok=True)


def run(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def find_wid():
    """Window browser terbesar (lewati helper kecil & clipboard)."""
    best, best_area = None, 0
    for w in run("xdotool", "search", "--name", "").splitlines():
        t = run("xdotool", "getwindowname", w)
        if not t or "clipboard" in t.lower():
            continue
        m = re.search(r"Geometry: (\d+)x(\d+)", run("xdotool", "getwindowgeometry", w))
        if not m:
            continue
        area = int(m.group(1)) * int(m.group(2))
        if area > best_area:
            best, best_area = w, area
    return best


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return run("xdotool", "getwindowname", WID)


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def typ(s):
    xdo("type", "--delay", "65", s)
    time.sleep(0.4)


def key(k):
    xdo("key", k)
    time.sleep(0.6)


def press_hold(seconds=8.0):
    """Gate PX: pendekatan mouse -> tekan-tahan dengan tremor natural -> lepas."""
    BX, BY = 660, 689
    out = run("xdotool", "getmouselocation")
    try:
        sx = int(out.split()[0].split(":")[1]); sy = int(out.split()[1].split(":")[1])
    except Exception:
        sx, sy = BX, BY
    print(f"  [hold] approach dari ({sx},{sy}) ke ({BX},{BY})")
    for i in range(1, 23):
        t = i / 22; e = 1 - (1 - t) ** 2.2
        xdo("mousemove", str(int(sx + (BX - sx) * e + random.uniform(-1.1, 1.1))),
            str(int(sy + (BY - sy) * e + random.uniform(-1.1, 1.1))))
        time.sleep(random.uniform(0.012, 0.03))
    xdo("mousemove", str(BX), str(BY)); time.sleep(0.35)
    xdo("mousemove", str(BX + random.randint(-3, 3)), str(BY - random.randint(3, 6)))
    time.sleep(random.uniform(0.06, 0.14))
    xdo("mousemove", str(BX), str(BY)); time.sleep(random.uniform(0.05, 0.12))

    xdo("mousedown", "1")
    t0, cx, cy, it = time.time(), float(BX), float(BY), 0
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-1.3, 1.3), BX - 18), BX + 18)
        cy = min(max(cy + random.uniform(-0.9, 0.9), BY - 5), BY + 5)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        time.sleep(random.uniform(0.03, 0.15) if random.random() > 0.15
                   else random.uniform(0.2, 0.45))
    print(f"  [hold] iterasi={it} dalam {time.time()-t0:.1f}s")
    shot("T_holding")
    xdo("mouseup", "1")
    time.sleep(random.uniform(0.1, 0.25))
    for i in range(1, 11):
        xdo("mousemove", str(BX + i * 9 + random.randint(-2, 2)),
            str(BY + i * 6 + random.randint(-2, 2)))
        time.sleep(0.02)


WID = find_wid()
if not WID:
    print("window tidak ketemu"); sys.exit(1)
print("WID:", WID, "|", title())
xdo("windowactivate", WID); time.sleep(0.8)

xdo("key", "ctrl+l"); time.sleep(0.6)
xdo("type", "--delay", "25", URL); time.sleep(0.5)
xdo("key", "Return"); time.sleep(11)
print("form:", title())
shot("K0_form")

email = f"x11k{random.randint(100000,999999)}@outlook.com"
pw = "Zx9kLmQ2vRt7pW!4"
print("email:", email)

# klik tengah kartu sekali supaya halaman punya fokus (hindari fokus di address bar)
xdo("mousemove", "640", "300"); time.sleep(0.2); xdo("click", "1"); time.sleep(0.5)

# --- step 1: email (auto-focus) ---
typ(email); shot("K1_email"); key("Return"); time.sleep(7)
print("after email:", title()); shot("K2_pw")

# --- step 2: password (auto-focus) ---
typ(pw); shot("K3_pw"); key("Return"); time.sleep(7)
print("after pw:", title()); shot("K4_details")

# --- step 3: birthdate. Field pertama pada step ini = Month dropdown.
shot("K5_before_birthdate")
# Tab ke Month (kalau belum fokus), buka, pilih, tutup
xdo("key", "Tab"); time.sleep(0.5)
xdo("key", "Down"); time.sleep(0.5)
xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
shot("K6_month")
xdo("key", "Tab"); time.sleep(0.5)
xdo("key", "Down"); time.sleep(0.5)
xdo("key", "Down"); time.sleep(0.4)
xdo("key", "Return"); time.sleep(1.2)
shot("K7_day")
xdo("key", "Tab"); time.sleep(0.5)
typ(str(random.randint(1988, 2000))); time.sleep(0.6)
shot("K8_birthdate")
xdo("key", "Return"); time.sleep(7)
print("after birthdate:", title()); shot("K9_name")

# --- step 4: nama ---
xdo("key", "Tab"); time.sleep(0.4)
typ(random.choice(["Nathan", "Bagas", "Rendy", "Fajar"])); time.sleep(0.5)
xdo("key", "Tab"); time.sleep(0.4)
typ(random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"])); time.sleep(0.6)
shot("K10_name")
xdo("key", "Return"); time.sleep(12)
t = title(); print("after submit:", t); shot("K11_submit")
if "prove" not in t.lower():
    time.sleep(10); t = title(); print("lagi:", t); shot("K12_wait")
if "prove" not in t.lower():
    print(">>> gate TIDAK muncul"); sys.exit(2)

print(">>> GATE MUNCUL")
time.sleep(2); shot("K13_gate")
press_hold(8.0)
time.sleep(3); print("after hold:", title()); shot("K14_after_hold")
time.sleep(12); print("final:", title()); shot("K15_final")
