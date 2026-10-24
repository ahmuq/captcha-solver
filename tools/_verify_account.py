#!/usr/bin/env python3
"""Verifikasi independen: apakah refresh token akun yang baru dibuat benar-benar hidup?

Membaca baris terakhir accounts/outlook_accounts.txt, menukar refresh token ke
Microsoft, lalu memanggil Graph /me. Kredensial TIDAK pernah dicetak — hanya status
dan panjang token, supaya output aman dibagikan.

Ini membuktikan akunnya nyata dan bisa dipakai, bukan sekadar "rt=true" dari bot.
"""
import json
import sys
import urllib.parse
import urllib.request

ACC = "/root/outlook-request/accounts/outlook_accounts.txt"
CLIENT = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"   # client_id publik Outlook (fallback)

line = ""
with open(ACC) as f:
    for l in f:
        l = l.strip()
        if l and "@" in l:
            line = l
if not line:
    print("tidak ada akun di file")
    sys.exit(1)

parts = line.split("|")
email = parts[0]
client_id = parts[2] if len(parts) > 2 and parts[2] else CLIENT
rt = parts[3] if len(parts) > 3 else ""
print(f"akun      : {email}")
print(f"client_id : {client_id}")
print(f"RT len    : {len(rt)}")

if not rt:
    print("RT kosong — tidak bisa diuji")
    sys.exit(1)

# 1. Tukar refresh token -> access token
data = urllib.parse.urlencode({
    "client_id": client_id,
    "grant_type": "refresh_token",
    "refresh_token": rt,
    "scope": "https://graph.microsoft.com/Mail.Read offline_access",
}).encode()
req = urllib.request.Request(
    "https://login.microsoftonline.com/consumers/oauth2/v2.0/token", data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"})
try:
    with urllib.request.urlopen(req, timeout=45) as r:
        tok = json.load(r)
except urllib.error.HTTPError as e:
    body = e.read().decode()[:300]
    print(f"\n[1] token exchange GAGAL: HTTP {e.code}")
    print(f"    {body}")
    sys.exit(1)
except Exception as e:
    print(f"\n[1] token exchange error: {e}")
    sys.exit(1)

at = tok.get("access_token") or ""
print(f"\n[1] token exchange OK: access_token len={len(at)} "
      f"expires_in={tok.get('expires_in')} scope={tok.get('scope','')[:60]}")

# 2. Panggil Graph /me — bukti mailbox benar-benar hidup
if at:
    req2 = urllib.request.Request(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": "Bearer " + at})
    try:
        with urllib.request.urlopen(req2, timeout=45) as r:
            me = json.load(r)
        print(f"[2] Graph /me OK: {me.get('userPrincipalName') or me.get('mail')}")
        print("\nKESIMPULAN: AKUN NYATA DAN AKTIF")
    except Exception as e:
        print(f"[2] Graph /me gagal: {e}")
        print("\nKESIMPULAN: token hidup, tapi /me gagal (cek scope)")
