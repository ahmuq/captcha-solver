"""Cari password kunci cookie yang dipakai biner CloakBrowser.

Chromium Linux menurunkan kunci AES dari password + iterasi + salt "saltysalt".
Biner ini tidak memuat literal "peanuts", jadi password-nya diganti. Strategi:
  1. kumpulkan kandidat string pendek dari .rodata biner (dan dari paket wrapper),
  2. coba setiap kandidat x iterasi (1, 1003, 1003*...) terhadap cookie _px3 nyata,
  3. laporkan kandidat yang menghasilkan plaintext token.
Kunci yang benar langsung terbukti dari bentuk plaintext-nya, jadi tidak ada tebakan.
"""
import hashlib
import re
import shutil
import sqlite3
import subprocess
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PROFILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh_profile"
TARGET = "_px3"


def load_target() -> bytes:
    tmp = "/tmp/_kt.db"
    shutil.copy2(f"{PROFILE}/Default/Cookies", tmp)
    con = sqlite3.connect(tmp)
    row = con.execute("select encrypted_value from cookies where name=?",
                      (TARGET,)).fetchone()
    con.close()
    return row[0]


def decrypt(blob: bytes, key: bytes):
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
        pt = pt[32:]          # Chromium >=24 menempelkan hash domain 32 byte
    try:
        return pt.decode("utf-8", "ignore")
    except Exception:
        return None


def candidates():
    """Kandidat password: literal umum + string pendek dari biner & wrapper."""
    base = ["peanuts", "", "chrome", "chromium", "cloakbrowser", "cloak",
            "ungoogled", "CloakBrowser", "secret", "password", "keyring"]
    for c in base:
        yield c
    # string pendek dari biner
    try:
        out = subprocess.run(["strings", "-a", "-n", "4", BIN],
                             capture_output=True, text=True, timeout=240).stdout
    except Exception:
        out = ""
    seen = set()
    for line in out.splitlines():
        s = line.strip()
        if 4 <= len(s) <= 40 and re.fullmatch(r"[A-Za-z0-9_\-\. ]+", s):
            if s not in seen:
                seen.add(s)
                yield s


blob = load_target()
print(f"target {TARGET}: {len(blob)} byte")
for iters in (1, 1003):
    n = 0
    for pw in candidates():
        n += 1
        if n > 400000:
            break
        key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", iters, dklen=16)
        val = decrypt(blob, key)
        if val and len(val) > 20:
            print(f"KETEMU! pw={pw!r} iters={iters} len={len(val)}")
            print(f"  plaintext head: {val[:40]!r}")
            sys.exit(0)
    print(f"  iters={iters}: {n} kandidat dicoba, belum ada")
print("tidak ada kandidat yang cocok")
