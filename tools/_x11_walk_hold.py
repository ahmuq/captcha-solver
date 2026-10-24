#!/usr/bin/env python3
"""Walker Outlook signup lewat X11 + press-hold biomekanik, untuk gate PX.

Pelajaran yang sudah terukur:
  * Protokol otomasi (CDP) membuat gate TIDAK PERNAH naik; X11 murni membuatnya naik.
  * `xdotool mousemove --sync` memblokir ~15s di halaman gate -> JANGAN dipakai.
  * Gerakan harus punya JALUR PENDEKATAN (approach path), bukan lompat langsung ke
    tombol: lompatan instan adalah tell, dan hold langsung ditolak PX.
"""
import os
import random
import subprocess
import sys
import time

os.environ["DISPLAY"] = ":99"
WID = os.environ.get("WID", "2097155")
SHOTS = "/tmp/x11shots"


def xdo(*a):
    subprocess.run(["xdotool", *a], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def title():
    return subprocess.run(["xdotool", "getwindowname", WID],
                          capture_output=True, text=True).stdout.strip()


def shot(n):
    subprocess.run(["import", "-window", WID, f"{SHOTS}/{n}.png"],
                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def geo():
    """Posisi jendela (untuk memetakan koordinat relatif jendela ke layar)."""
    out = subprocess.run(["xdotool", "getwindowgeometry", WID],
                         capture_output=True, text=True).stdout
    pos = [l for l in out.splitlines() if "Position" in l][0]
    parts = pos.split(":")[1].strip().split()[0]
    x, y = parts.split(",")
    return int(x), int(y)


def move_smooth(tx, ty, steps=18, jitter=1.4):
    """Gerak pointer bertahap dengan easing + jitter, dari posisi sekarang ke target."""
    out = subprocess.run(["xdotool", "getmouselocation"],
                         capture_output=True, text=True).stdout
    try:
        cur = out.split()[0].split(":")[1], out.split()[1].split(":")[1]
        sx, sy = int(cur[0]), int(cur[1])
    except Exception:
        sx, sy = tx, ty

    for i in range(1, steps + 1):
        t = i / steps
        # ease-out: cepat di awal, melambat mendekati target (seperti tangan manusia)
        e = 1 - (1 - t) ** 2.2
        x = sx + (tx - sx) * e + random.uniform(-jitter, jitter)
        y = sy + (ty - sy) * e + random.uniform(-jitter, jitter)
        xdo("mousemove", str(int(x)), str(int(y)))
        time.sleep(random.uniform(0.012, 0.035))
    xdo("mousemove", str(tx), str(ty))
    time.sleep(random.uniform(0.15, 0.35))


def press_hold(bx, by, seconds=8.0):
    """Pendekatan -> turunkan -> tahan dengan tremor natural -> lepas -> gerak pergi."""
    print(f"  [hold] mendekati tombol ({bx},{by})")
    move_smooth(bx, by, steps=20)

    # sentuhan: turun sedikit dari atas, lalu ke pusat
    xdo("mousemove", str(bx + random.randint(-3, 3)), str(by - random.randint(3, 6)))
    time.sleep(random.uniform(0.06, 0.14))
    xdo("mousemove", str(bx), str(by))
    time.sleep(random.uniform(0.04, 0.10))

    xdo("mousedown", "1")
    print(f"  [hold] mousedown, tahan ~{seconds}s")
    t0 = time.time()
    cx, cy = float(bx), float(by)
    it = 0
    while time.time() - t0 < seconds:
        cx = min(max(cx + random.uniform(-1.3, 1.3), bx - 18), bx + 18)
        cy = min(max(cy + random.uniform(-0.9, 0.9), by - 5), by + 5)
        xdo("mousemove", str(int(cx)), str(int(cy)))
        it += 1
        # tremor tidak seragam: kadang jeda, kadang cepat
        time.sleep(random.uniform(0.03, 0.15) if random.random() > 0.15
                   else random.uniform(0.2, 0.45))
    print(f"  [hold] iterasi={it} dalam {time.time()-t0:.1f}s")
    shot("H1_holding")
    xdo("mouseup", "1")
    # gerak pergi setelah lepas (manusia tidak berhenti diam)
    time.sleep(random.uniform(0.1, 0.25))
    move_smooth(bx + random.randint(60, 120), by + random.randint(40, 90), steps=10)


def type_text(s):
    xdo("type", "--delay", "70", s)


def main():
    print("judul:", title())
    xdo("windowactivate", WID)
    time.sleep(0.8)

    email = f"x11walk{random.randint(10000,99999)}@outlook.com"
    pw = "Zx9kLmQ2vRt7pW!4"
    print(f"email: {email}")

    # --- step 1: email (field pertama sudah fokus) ---
    move_smooth(640, 470, steps=12)
    xdo("click", "1")
    time.sleep(0.5)
    type_text(email)
    time.sleep(0.8)
    shot("W1_email")
    xdo("key", "Return")
    time.sleep(6)
    print("setelah email:", title())
    shot("W2_password_step")

    # --- step 2: password ---
    move_smooth(640, 470, steps=12)
    xdo("click", "1")
    time.sleep(0.5)
    type_text(pw)
    time.sleep(0.8)
    xdo("key", "Return")
    time.sleep(6)
    print("setelah password:", title())
    shot("W3_details_step")

    # --- step 3: birthdate (dropdown Fluent: klik, pilih dengan Down+Enter) ---
    for name, (x, y) in [("month", (516, 536)), ("day", (639, 536))]:
        move_smooth(x, y, steps=10)
        xdo("click", "1")
        time.sleep(1.2)
        xdo("key", "Down")
        time.sleep(0.3)
        xdo("key", "Down")
        time.sleep(0.3)
        xdo("key", "Return")
        time.sleep(1.0)
        print(f"  {name} dipilih")
    move_smooth(760, 536, steps=10)
    xdo("click", "1")
    time.sleep(0.6)
    type_text(str(random.randint(1988, 2000)))
    time.sleep(1.0)
    shot("W4_birthdate")
    move_smooth(640, 710, steps=10)
    xdo("click", "1")
    time.sleep(6)
    print("setelah birthdate:", title())
    shot("W5_name_step")

    # --- step 4: nama ---
    move_smooth(650, 432, steps=10)
    xdo("click", "1")
    time.sleep(0.5)
    type_text(random.choice(["Nathan", "Bagas", "Rendy", "Fajar"]))
    time.sleep(0.6)
    move_smooth(650, 512, steps=10)
    xdo("click", "1")
    time.sleep(0.5)
    type_text(random.choice(["Kusumo", "Pratama", "Santoso", "Wijaya"]))
    time.sleep(0.8)
    shot("W6_name_filled")

    # submit -> gate PX harusnya muncul di sini
    move_smooth(650, 722, steps=10)
    xdo("click", "1")
    time.sleep(10)
    t = title()
    print("setelah submit:", t)
    shot("W7_after_submit")

    if "prove" not in t.lower():
        time.sleep(10)
        t = title()
        print("judul lagi:", t)
        shot("W8_wait")

    if "prove" not in t.lower():
        print(">>> gate TIDAK muncul, berhenti")
        return 1

    print(">>> GATE MUNCUL — tekan dan tahan")
    time.sleep(2)
    shot("W9_gate")
    press_hold(660, 689, seconds=8.0)

    time.sleep(3)
    print("setelah hold:", title())
    shot("W10_after_hold")
    time.sleep(12)
    print("akhir:", title())
    shot("W11_final")
    return 0


if __name__ == "__main__":
    sys.exit(main())
