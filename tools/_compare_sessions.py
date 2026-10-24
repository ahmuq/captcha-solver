#!/usr/bin/env python3
"""Kenapa captchaNotRendered? Bandingkan sesi PX: mana yang render, mana yang tidak.

Yang dibandingkan per sesi (dikelompokkan per `_pxvid`, penanda satu visitor):
  - jumlah panggilan captcha.js (retry render)
  - ada/tidak panggilan stk.hsprotect.net/ns (jebakan?)
  - panggilan collector /api/v2/msft (laporan hasil)
  - ada/tidak clientError captchaNotRendered
  - urutan waktu relatif
"""
import json
import os
import urllib.parse

p = "/tmp/px_net.jsonl"
rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []

# kelompokkan per index.html (satu sesi = satu navigasi iframe)
sessions = []
for r in rows:
    u = r.get("url", "")
    if "iframe.hsprotect.net/index.html" in u and r["m"] == "Network.requestWillBeSent":
        sid = urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("session_id",
                                                                        [""])[0]
        sessions.append({"t": r["t"], "session_id": sid, "ev": []})

if sessions:
    for r in rows:
        u = r.get("url", "")
        for s in sessions:
            if r["t"] >= s["t"]:
                s["ev"].append((r["t"], r["m"], u))

for i, s in enumerate(sessions, 1):
    cap = sum(1 for t, m, u in s["ev"] if "captcha.js" in u)
    stk = sum(1 for t, m, u in s["ev"] if "stk.hsprotect.net" in u)
    msft = sum(1 for t, m, u in s["ev"] if "/api/v2/msft" in u)
    cerr = [u for t, m, u in s["ev"] if "clientError" in u]
    nrend = sum(1 for t, m, u in s["ev"] if "captchaNotRendered" in u)
    bundle = sum(1 for t, m, u in s["ev"] if "assets/js/bundle" in u)
    print(f"--- sesi {i} --- session_id={s['session_id'][:20]}...")
    print(f"    captcha.js={cap}  bundle={bundle}  stk/ns={stk}  msft={msft}  "
          f"clientError={len(cerr)}  notRendered={nrend}")
    if cerr:
        raw = urllib.parse.parse_qs(urllib.parse.urlparse(cerr[0]).query).get("r",
                                                                             [""])[0]
        try:
            d = json.loads(raw)
            print(f"    pesan: {d.get('message')!r}  stack={d.get('stack')!r}")
        except Exception:
            pass

print()
print("=== RINGKASAN ===")
print(f"total sesi       : {len(sessions)}")
print(f"sesi render gagal: {sum(1 for s in sessions if any('captchaNotRendered' in u for _, _, u in s['ev']))}")
print(f"total captcha.js : {sum(1 for r in rows if 'captcha.js' in r.get('url', ''))}")
print(f"total bundle     : {sum(1 for r in rows if 'assets/js/bundle' in r.get('url', ''))}")
print()
print("catatan: bundle dimuat berulang = captcha.js gagal dieksekusi lalu dicoba lagi")
