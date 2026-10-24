"""Uji: store dari sesi --password-store=basic bisa didekripsi dengan 'peanuts'?

Kalau ya, jalur X11 bisa memanen cookie tanpa CDP: jalankan browser dengan
--password-store=basic, lalu dekripsi store-nya dengan password default Chromium.
"""
import hashlib
import shutil
import sqlite3
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PROFILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/cryptotest"


def try_decrypt(blob: bytes, key: bytes):
    if not blob.startswith(b"v10"):
        return blob.decode("utf-8", "ignore") if blob else None
    body = blob[3:]
    if len(body) < 28:
        return None
    try:
        pt = AESGCM(key).decrypt(body[:12], body[12:], None)
    except Exception:
        return None
    if len(pt) > 32:
        pt = pt[32:]
    return pt.decode("utf-8", "ignore")


tmp = "/tmp/_basic_ck.db"
shutil.copy2(f"{PROFILE}/Default/Cookies", tmp)
con = sqlite3.connect(tmp)
rows = con.execute("select name,host_key,encrypted_value from cookies").fetchall()
con.close()
print(f"baris cookie: {len(rows)}")
if not rows:
    print("store kosong — buka situs yang benar-benar menyetel cookie")
    sys.exit(1)

for pw in ("peanuts", "", "chrome"):
    for iters in (1, 1003):
        key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", iters, dklen=16)
        hits = []
        for name, host, enc in rows:
            v = try_decrypt(enc or b"", key)
            if v and len(v) >= 4:
                hits.append((name, host, v[:24]))
        if hits:
            print(f"COCOK pw={pw!r} iters={iters}: {len(hits)} cookie terbaca")
            for h in hits[:5]:
                print(f"   {h[0]:14} {h[1]:16} {h[2]!r}")
            sys.exit(0)
        print(f"  pw={pw!r} iters={iters}: 0 terbaca")

print("tidak ada yang cocok — kunci masih kustom")
