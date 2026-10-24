#!/usr/bin/env python3
"""Uji apakah iframe challenge merender gate dengan session_id NYATA dari bot.

Screenshot sesi bot terakhir menunjukkan halaman blank dengan session_id
7f8fcf518f384a7b8df150641fcaafd9 (tanpa dash). Hipotesis: format session_id harus
ber-dash (UUID), karena bot sendiri memformatnya begitu di buildChallengeIframeURL.

Uji: buka iframe dengan kedua format, bandingkan apakah gate render.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser          # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
SID_RAW = sys.argv[1] if len(sys.argv) > 1 else "7f8fcf518f384a7b8df150641fcaafd9"


def dashed(s):
    if len(s) == 32 and "-" not in s:
        return f"{s[:8]}-{s[8:12]}-{s[12:16]}-{s[16:20]}-{s[20:]}"
    return s


for label, sid in (("tanpa-dash", SID_RAW), ("ber-dash", dashed(SID_RAW))):
    url = f"https://iframe.hsprotect.net/index.html?app_id=PXzC5j78di&session_id={sid}"
    profile = f"/tmp/px_dash_{label}_{int(time.time())}"
    print(f"\n=== {label}: session_id={sid} ===")
    print(f"    url: {url}")
    br = Browser(profile, proxy=PROXY)
    try:
        br.start(url, 17.0)
        wid = br.window_id()
        if not wid:
            print("    window tidak ketemu")
            continue
        title = br.title(wid)
        print(f"    title: {title!r}")
        shot = f"/tmp/px_dash_{label}.png"
        br.screenshot(shot, wid)
        print(f"    screenshot: {shot}")
        # ukur konten: apakah ada elemen non-putih?
        out = subprocess.run(
            ["convert", shot, "-colorspace", "Gray", "-format",
             "%[fx:standard_deviation]", "info:"],
            capture_output=True, text=True).stdout.strip()
        print(f"    std-dev gambar: {out} (blank ~0.0)")
    finally:
        br.stop()
        subprocess.run(["rm", "-rf", profile], check=False)
