"""Panen cookie PX dari SQLite store profil Chromium (jalur X11 tanpa CDP).

Kenapa perlu: pada jalur X11 tidak ada CDP, jadi `context.cookies()` tidak tersedia.
Cookie dibaca langsung dari `<profile>/Default/Cookies`.

Format: Chromium menyimpan `encrypted_value` sebagai v10 -> AES-256-GCM
(12-byte nonce, 16-byte tag). Kunci berasal dari keyring OS; pada sesi tanpa
keyring (Xvfb/headless) Chromium memakai password bawaan "peanuts" dengan
iterasi PBKDF2 1 dan salt "saltysalt". Kandidat kunci diuji terhadap cookie
nyata, jadi kita tidak menebak: kunci yang benar menghasilkan plaintext _px3
yang berbentuk token.
"""
from __future__ import annotations

import hashlib
import sqlite3
import shutil
import subprocess
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PX_NAMES = ("_px3", "_pxvid", "_pxde", "pxcts", "_px2", "pxhd")
CANDIDATE_PASSWORDS = ("peanuts", "", "chrome")


def _derive_keys():
    """Kunci kandidat dari password+iterasi+salt yang lazim di Chromium Linux."""
    out = []
    for pw in CANDIDATE_PASSWORDS:
        for iters in (1, 1, 1003):
            try:
                out.append((pw, iters, hashlib.pbkdf2_hmac(
                    "sha1", pw.encode(), b"saltysalt", iters, dklen=16)))
            except Exception:
                pass
    return out


def _decrypt(blob: bytes, key: bytes) -> str | None:
    if not blob.startswith(b"v10") and not blob.startswith(b"v11"):
        try:
            return blob.decode("utf-8")
        except Exception:
            return None
    body = blob[3:]
    if len(body) < 28:
        return None
    nonce, ct = body[:12], body[12:]
    try:
        pt = AESGCM(key).decrypt(nonce, ct, None)
    except Exception:
        return None
    try:
        # Chromium >= v24 (Linux) menempelkan 32 byte SHA256 dari domain di depan.
        if len(pt) > 32:
            stripped = pt[32:]
            if stripped and all(32 <= b < 127 for b in stripped[:8]):
                return stripped.decode("utf-8", "ignore")
        return pt.decode("utf-8", "ignore")
    except Exception:
        return None


def read_cookies(profile_dir: str, host_contains: str = "hsprotect") -> dict:
    """Buka store cookie profil, dekripsi entri PX, kembalikan {nama: nilai}.

    Store disalin dulu ke file sementara supaya tidak mengunci profil yang sedang
    dipakai browser (SQLite bisa terkunci).
    """
    src = f"{profile_dir}/Default/Cookies"
    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(src, tmp)
    subprocess.run(["chmod", "600", tmp], check=False)
    rows = []
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "select name, host_key, encrypted_value, value from cookies").fetchall()
        con.close()
    finally:
        try:
            subprocess.run(["rm", "-f", tmp], check=False)
        except Exception:
            pass

    keys = _derive_keys()
    out, key_used = {}, None
    for name, host, enc, plain in rows:
        if host_contains not in (host or ""):
            continue
        if plain:
            out[name] = plain
            continue
        for pw, iters, key in keys:
            val = _decrypt(enc or b"", key)
            if val and len(val) > 8:
                out[name] = val
                key_used = (pw, iters)
                break
    return {"cookies": out, "key": key_used, "total_rows": len(rows)}


def cookie_header(cookies: dict) -> str:
    """Header siap pakai untuk replay; urutan pxcts->_pxvid->_px3 seperti README."""
    order = ["pxcts", "_pxvid", "_px3", "_pxde"]
    parts = [f"{n}={cookies[n]}" for n in order if n in cookies]
    for n, v in cookies.items():
        if n not in order:
            parts.append(f"{n}={v}")
    return "; ".join(parts)


if __name__ == "__main__":
    import json
    import sys

    prof = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh_profile"
    res = read_cookies(prof)
    c = res["cookies"]
    print(f"profil      : {prof}")
    print(f"baris cookie: {res['total_rows']}")
    print(f"kunci cocok : {res['key']}")
    print(f"nama PX     : {sorted(c)}")
    for n in sorted(c):
        v = c[n]
        print(f"  {n:8} len={len(v):4} head={v[:16]!r}")
    hdr = cookie_header(c)
    print(f"header      : {len(hdr)} byte")
    json.dump(c, open("/tmp/px_cookies.json", "w"), indent=1)
    print("ditulis ke /tmp/px_cookies.json")
