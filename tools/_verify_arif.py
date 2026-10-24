#!/usr/bin/env python3
"""Verifikasi apakah akun yang "sukses" itu benar-benar hidup (refresh token valid).

Tidak mencetak token/credential apa pun — hanya status hidup/mati.
"""
import json
import sys
import urllib.parse
import urllib.request

LINE = sys.argv[1] if len(sys.argv) > 1 else ""
if not LINE:
    # ambil akun arif.permana1995 dari file
    for ln in open("/root/outlook-request/accounts/outlook_accounts.txt"):
        if ln.startswith("arif.permana1995@outlook.co.id|"):
            LINE = ln.strip()
            break
if not LINE:
    print("akun tidak ditemukan")
    raise SystemExit(1)

email, pwd, client_id, rt = LINE.split("|")[:4]
print(f"akun    : {email}")
print(f"client  : {client_id[:8]}...")
print(f"rt len  : {len(rt)}")

# Tukar refresh token -> access token (bukti akun hidup)
data = urllib.parse.urlencode({
    "client_id": client_id,
    "grant_type": "refresh_token",
    "refresh_token": rt,
    "scope": "https://outlook.office.com/.default openid profile offline_access",
}).encode()
req = urllib.request.Request(
    "https://login.live.com/oauth20_token.srf", data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"})
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.load(r)
    at = j.get("access_token") or ""
    print(f"\nHASIL: HIDUP — access_token diterima (len={len(at)})")
    print(f"  refresh_token baru: {'ya' if j.get('refresh_token') else 'tidak'}")
    print(f"  expires_in: {j.get('expires_in')}")

    # Cek identitas via Graph
    g = urllib.request.Request("https://graph.microsoft.com/v1.0/me",
                               headers={"Authorization": f"Bearer {at}"})
    with urllib.request.urlopen(g, timeout=45) as r2:
        me = json.load(r2)
    print(f"  Graph /me: {me.get('userPrincipalName') or me.get('mail')}")
except Exception as e:
    body = ""
    if hasattr(e, "read"):
        try:
            body = e.read().decode()[:300]
        except Exception:
            pass
    print(f"\nHASIL: MATI/INVALID — {e}")
    if body:
        print(f"  respons: {body}")
