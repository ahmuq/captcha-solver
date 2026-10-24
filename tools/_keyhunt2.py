"""Pencarian kunci cookie yang lebih luas: password x salt x iterasi x panjang kunci.

Blob _px3 berukuran 675 byte = 3 (v10) + 12 (nonce GCM) + 644 + 16 (tag), jadi
memang AES-GCM. Yang belum diketahui: password, salt, iterasi, dan panjang kunci.
Uji terhadap cookie nyata dari sesi github/wikipedia (bukan sesi Microsoft), lalu
terapkan ke _px3 begitu kuncinya ketemu.
"""
import hashlib
import itertools
import shutil
import sqlite3
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/_c3.db"

shutil.copy2(DB, "/tmp/_ks.db")
con = sqlite3.connect("/tmp/_ks.db")
rows = con.execute("select name,host_key,encrypted_value from cookies").fetchall()
con.close()
print(f"kandidat cookie untuk kalibrasi: {len(rows)}")


def dec(blob: bytes, key: bytes):
    if not blob.startswith(b"v10"):
        return None
    body = blob[3:]
    if len(body) < 28:
        return None
    try:
        pt = AESGCM(key).decrypt(body[:12], body[12:], None)
    except Exception:
        return None
    if len(pt) > 32:
        pt = pt[32:]
    try:
        return pt.decode("utf-8", "ignore")
    except Exception:
        return None


PASSWORDS = ["peanuts", "", "chrome", "chromium", "cloakbrowser", "CloakBrowser",
             "cloak", "ungoogled", "salt", "sodium", "keyring", "basic"]
SALTS = [b"saltysalt", b"salt", b"cloakbrowser", b"cloaksalt", b"", b"sodium",
         b"chromium", b"ungoogled"]
ITERS = [1, 1003, 1004, 1005, 1007, 1008, 1009, 1013]
DK = [16, 32]

found = None
n = 0
for pw, salt, it, dk in itertools.product(PASSWORDS, SALTS, ITERS, DK):
    n += 1
    key = hashlib.pbkdf2_hmac("sha1", pw.encode(), salt, it, dklen=dk)
    for name, host, enc in rows:
        v = dec(enc or b"", key)
        if v and len(v) >= 3 and v.isprintable():
            print(f"KETEMU: pw={pw!r} salt={salt!r} iters={it} dk={dk}")
            print(f"  {name} @ {host} -> {v[:40]!r}")
            found = (pw, salt, it, dk)
            break
    if found:
        break
print(f"dicoba {n} kombinasi; hasil: {found or 'tidak ada'}")
