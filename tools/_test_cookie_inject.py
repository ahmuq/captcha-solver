#!/usr/bin/env python3
"""Uji apakah cookie bisa disuntikkan ke profil Chromium lewat kolom `value`.

Chromium menyimpan cookie terenkripsi di `encrypted_value`, tapi kolom `value`
(plaintext) tetap dibaca bila `encrypted_value` kosong. Kalau ini bekerja, solver
bisa membawa `_pxvid`/`_px3` milik caller ke dalam browser-nya sendiri — yang
kemungkinan besar jadi syarat PX mau merender challenge untuk sesi itu.
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import harvest_cookies   # noqa: E402

PROFILE = f"/tmp/_ckinj_{int(time.time())}"
shutil.rmtree(PROFILE, ignore_errors=True)
os.makedirs(PROFILE, exist_ok=True)

# 1. buat store dengan menjalankan browser sebentar lalu SIGTERM (store dibuat saat flush)
from perimeterx.browser import Browser   # noqa: E402

br = Browser(PROFILE, proxy=None)
br.start("https://example.com", 12.0)
br.stop()
time.sleep(2)

store = os.path.join(PROFILE, "Default", "Cookies")
print("store ada:", os.path.exists(store))
if not os.path.exists(store):
    sys.exit(1)

# 2. suntikkan cookie plaintext
TEST = {"name": "_pxvid", "value": "test-visitor-id-12345",
        "domain": ".hsprotect.net", "path": "/"}
con = sqlite3.connect(store)
cur = con.cursor()
cur.execute("""INSERT OR REPLACE INTO cookies
  (creation_utc, host_key, top_frame_site_key, name, value, encrypted_value,
   path, expires_utc, is_secure, is_httponly, last_access_utc, has_expires,
   is_persistent, priority, samesite, source_scheme, source_port,
   last_update_utc, source_type, has_cross_site_ancestor)
  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(time.time() * 1e6), TEST["domain"], "", TEST["name"], TEST["value"],
             b"", TEST["path"], int((time.time() + 86400) * 1e6), 1, 0,
             int(time.time() * 1e6), 1, 1, 1, 0, 2, 443,
             int(time.time() * 1e6), 0, 0))
con.commit()
con.close()
print("cookie disuntikkan")

# 3. panen ulang lewat CDP dan lihat apakah cookie muncul
res = harvest_cookies(PROFILE)
print("hasil panen:", {k: v for k, v in res.items() if k != "cookies"})
found = (res.get("cookies") or {}).get("_pxvid")
print(f"_pxvid terbaca kembali: {found!r}")
print("KESIMPULAN:", "INJEKSI BEKERJA" if found == TEST["value"] else "INJEKSI GAGAL")
shutil.rmtree(PROFILE, ignore_errors=True)
