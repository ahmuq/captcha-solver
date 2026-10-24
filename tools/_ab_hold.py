#!/usr/bin/env python3
"""A/B: pola hold LAMA vs BARU — mana yang lebih sering diterima PX?

Latar: satu akun pernah sukses (arif.permana1995@outlook.co.id) pada percobaan #2
dengan solver versi LAMA (hold 9s, mendarat langsung di tombol). Setelah itu pola hold
diubah (hover-lalu-mendarat, 5s) demi menghilangkan captchaNotRendered — tapi belum
pernah dibandingkan secara langsung. Sekarang PX mengirim vonis eksplisit
({"type":"succeeded"} / {"type":"failed"}), jadi perbandingannya objektif.

Setiap sesi memakai challenge NYATA (session_id/uuid/vid dari alur live); ID palsu
membuat captcha.js tidak dimuat dan vonisnya palsu.

Pakai: _ab_hold.py <jumlah_sesi_per_pola> [session_id uuid vid]
Hasil ditulis ke /tmp/px_ab3.jsonl (append) supaya bisa dipantau sementara berjalan.
"""
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser                            # noqa: E402
from perimeterx.sessionless import _Wrapper, _find_gate_button     # noqa: E402
from perimeterx.x11 import Hand, DT                                # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3
OUT = "/tmp/px_ab3.jsonl"
# Ambil beberapa challenge BERBEDA dari metadata alur live. Hipotesis yang diuji:
# challenge PX sekali pakai — uji yang berhasil memakai session_id ini untuk PERTAMA
# kali, sedangkan pemakaian ulang tidak pernah menghasilkan vonis.
def _challenges(n):
    """Challenge dari metadata live, HANYA yang belum pernah dicoba.

    Challenge PX sekali pakai: memakai ulang session_id tidak pernah menghasilkan vonis
    (terukur 0 dari 10), dan hasilnya menyamar sebagai "no-button"/"no-window" sehingga
    percobaan terlihat seperti kegagalan kode padahal cuma challenge basi. Semua sid yang
    sudah ada di file hasil dianggap terpakai.
    """
    import re
    used = set()
    try:
        for line in open(OUT):
            try:
                used.add(json.loads(line).get("sid"))
            except Exception:
                continue
    except FileNotFoundError:
        pass
    txt = open("/tmp/px_challenge_meta.json").read()
    urls = re.findall(r'"challengeUrl":"([^"]+)"', txt)
    uuids = re.findall(r'"uuid":"([^"]+)"', txt)
    vids = re.findall(r'"vid":"([^"]+)"', txt)
    out, seen = [], set()
    for u, uu, vv in zip(urls, uuids, vids):
        sid = u.replace("\\u0026", "&").split("session_id=")[-1]
        if sid in seen or sid[:13] in used:
            continue
        seen.add(sid)
        out.append((sid, uu, vv))
    if len(out) < n:
        print(f"PERINGATAN: hanya {len(out)} challenge segar (butuh {n})", flush=True)
    return out[:n] if n else out


CHALLENGES = _challenges(0)
SID = UUID = VID = None


def hold_old(hand, x, y, secs=9.0):
    """Pola LAMA: langsung mendarat di tombol, jiggle 1-3 px, hold 9 s."""
    hand.move_to(x, y)
    hand.idle(random.uniform(0.35, 0.9))
    hand.move_to(x - random.uniform(1, 3), y - random.uniform(2, 5), duration=0.12)
    time.sleep(random.uniform(0.02, 0.06))
    hand.press()
    t0 = time.perf_counter()
    n = 0
    while time.perf_counter() - t0 < secs:
        el = time.perf_counter() - t0
        tx, ty = hand._tremor(el)
        dx, dy = hand._drift_step()
        hand._emit(x + tx + dx, y + ty + dy)
        n += 1
        if n % 4 == 0:
            hand.d.sync()
        time.sleep(DT)
    hand.d.sync()
    held = time.perf_counter() - t0
    hand.release()
    return held, hand.emitted


def hold_new(hand, x, y, secs=5.0):
    """Pola BARU: hover dari offset lalu mendarat di tombol, hold 5 s."""
    hand.move_instant(x - random.uniform(110, 150), y - random.uniform(50, 70))
    time.sleep(random.uniform(0.2, 0.35))
    hand.move_to(x, y, duration=random.uniform(0.35, 0.55))
    hand.idle(random.uniform(0.25, 0.5))
    hand.press()
    t0 = time.perf_counter()
    n = 0
    while time.perf_counter() - t0 < secs:
        el = time.perf_counter() - t0
        tx, ty = hand._tremor(el)
        dx, dy = hand._drift_step()
        hand._emit(x + tx + dx, y + ty + dy)
        n += 1
        if n % 4 == 0:
            hand.d.sync()
        time.sleep(DT)
    hand.d.sync()
    held = time.perf_counter() - t0
    hand.release()
    return held, hand.emitted


def hold_still(hand, x, y, secs=4.0):
    """Pola DIAM: hover masuk ke tombol, tekan, tahan TANPA gerakan sama sekali.

    Ini pola yang TERBUKTI menghasilkan {"type":"succeeded"} pada uji _hold_register:
    di sana pointer ditekan lalu hanya tidur + screenshot selama 4 s tanpa satu pun
    mousemove. Hipotesis: PX menilai stabilitas saat ditahan, dan tremor 100 Hz justru
    membuat jejaknya terbaca sintetis.
    """
    hand.move_instant(x - random.uniform(110, 150), y - random.uniform(50, 70))
    time.sleep(random.uniform(0.2, 0.35))
    hand.move_to(x, y, duration=random.uniform(0.35, 0.55))
    time.sleep(random.uniform(0.4, 0.6))
    hand.press()
    t0 = time.perf_counter()
    time.sleep(secs)               # diam total: tidak ada event motion
    hand.d.sync()
    held = time.perf_counter() - t0
    hand.release()
    return held, 0


def one_session(pattern: str, idx: int) -> dict:
    sid, uuid, vid = CHALLENGES[(idx - 1) % len(CHALLENGES)]
    profile = f"/tmp/_ab_{pattern}_{idx}_{int(time.time())}"
    wrap = _Wrapper(f"https://iframe.hsprotect.net/index.html?app_id={APP}"
                    f"&session_id={sid}", uuid, vid)
    br = Browser(profile, proxy=PROXY)
    rec = {"pattern": pattern, "idx": idx, "verdict": "none", "rendered": False,
           "button": None, "hz": 0, "sid": sid[:13]}
    try:
        br.start(wrap.url, 17.0)
        wid = br.window_id()
        if not wid:
            rec["verdict"] = "no-window"
            return rec
        t0 = time.time()
        while time.time() - t0 < 30 and not wrap.rendered.is_set():
            time.sleep(1)
        rec["rendered"] = wrap.rendered.is_set()
        box = _find_gate_button(br, wid, br.height)
        rec["button"] = box
        if not box:
            rec["verdict"] = "no-button"
            return rec
        hand = Hand()
        fn = {"old": hold_old, "new": hold_new, "still": hold_still}[pattern]
        held, emitted = fn(hand, box[0], box[1])
        rec["hz"] = round(emitted / max(held, 0.01))
        rec["held"] = round(held, 1)
        # Tunggu vonis PX
        t0 = time.time()
        while time.time() - t0 < 40:
            if wrap.solved.is_set() or wrap.failed.is_set():
                break
            time.sleep(0.5)
        if wrap.solved.is_set():
            rec["verdict"] = "SUCCEEDED"
        elif wrap.failed.is_set():
            rec["verdict"] = "failed"
        rec["events"] = sorted({str((e.get("data") or {}).get("type"))
                                for e in wrap.events
                                if isinstance(e.get("data"), dict)})
    except Exception as e:                                     # noqa: BLE001
        rec["verdict"] = f"error: {e}"
    finally:
        br.stop()
        wrap.close()
        subprocess.run(["rm", "-rf", profile], check=False)
    return rec


for pattern in ("still",):
    for i in range(1, N + 1):
        r = one_session(pattern, i)
        with open(OUT, "a") as f:
            f.write(json.dumps(r) + "\n")
        print(f"{pattern:4} #{i}: {r['verdict']:10} sid={r.get('sid')} rendered={r['rendered']} "
              f"btn={r['button']} {r.get('hz')}Hz events={r.get('events')}", flush=True)
