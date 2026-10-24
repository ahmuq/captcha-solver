#!/usr/bin/env python3
"""Cari path cookie store sebenarnya di profil Chromium ini."""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"
from perimeterx.browser import Browser   # noqa: E402

PROFILE = f"/tmp/_ckpath_{int(time.time())}"
shutil.rmtree(PROFILE, ignore_errors=True)
br = Browser(PROFILE, proxy=None)
br.start("https://example.com", 12.0)
br.stop()
time.sleep(2)

print("=== semua file bernama Cookies / *Cookies* di profil ===")
for root, dirs, files in os.walk(PROFILE):
    for f in files:
        if "ookie" in f and f != "SingletonCookie":
            p = os.path.join(root, f)
            print(f"  {p}  ({os.path.getsize(p)} byte)")

print("\n=== struktur direktori tingkat 2 ===")
for d in sorted(os.listdir(PROFILE))[:12]:
    p = os.path.join(PROFILE, d)
    if os.path.isdir(p):
        print(f"  {d}/ -> {sorted(os.listdir(p))[:8]}")

shutil.rmtree(PROFILE, ignore_errors=True)
