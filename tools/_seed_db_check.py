#!/usr/bin/env python3
"""Diagnosis: apakah cookie/localStorage hasil seeding benar-benar tersimpan ke disk?

Membaca store SQLite langsung (tanpa dekripsi — hanya keberadaan nama cookie), lalu
membandingkan dengan hasil harvest lewat CDP. Ini memisahkan dua kemungkinan:
  (a) seeding tidak pernah ditulis ke disk, atau
  (b) tertulis tapi halaman challenge menimpanya.
"""
import os
import sqlite3
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import harvest_cookies     # noqa: E402
from perimeterx.seed import seed_visitor           # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
VID = "33787df6-c977-11f1-b097-31232c7aa85c"
PROFILE = f"/tmp/_seeddbg_{int(time.time())}"

rep = seed_visitor(PROFILE, APP, VID, PROXY)
print("seeding:", {k: rep.get(k) for k in ("seeded","cookie","localstorage","in_memory_pxvid","cookie_visible_to_js","error")})

# 1. store cookie di disk
store = os.path.join(PROFILE, "Default", "Cookies")
print(f"\nstore ada: {os.path.exists(store)}")
if os.path.exists(store):
    try:
        con = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
        rows = list(con.execute(
            "SELECT host_key, name, length(value), length(encrypted_value) "
            "FROM cookies WHERE name LIKE '%px%'"))
        print(f"cookie PX di store: {len(rows)}")
        for h, n, lv, le in rows:
            print(f"   {h:24} {n:8} value={lv} enc={le}")
        con.close()
    except Exception as e:
        print("baca store gagal:", e)

# 2. localStorage di disk
ls_dir = os.path.join(PROFILE, "Default", "Local Storage", "leveldb")
if os.path.isdir(ls_dir):
    files = sorted(os.listdir(ls_dir))
    print(f"\nLocal Storage leveldb: {len(files)} file -> {files[:4]}")
    tot = sum(os.path.getsize(os.path.join(ls_dir, f)) for f in files
              if os.path.isfile(os.path.join(ls_dir, f)))
    print(f"total ukuran: {tot} byte")
else:
    print("\nLocal Storage leveldb: TIDAK ADA")

# 3. harvest lewat CDP (metode yang terbukti) untuk melihat apa yang dibaca browser
har = harvest_cookies(PROFILE)
got = (har.get("cookies") or {}).get("_pxvid")
print(f"\nharvest CDP: _pxvid={got!r} total={har.get('total')}")
print("KESIMPULAN:", "PERSIST OK" if got == VID else "TIDAK PERSIST / tertimpa")

import subprocess   # noqa: E402
subprocess.run(["rm", "-rf", PROFILE], check=False)
