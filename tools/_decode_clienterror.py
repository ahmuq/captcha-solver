#!/usr/bin/env python3
"""Decode laporan clientError PX — PX menyebutkan sendiri apa yang salah."""
import json
import os
import urllib.parse

p = "/tmp/px_net.jsonl"
rows = [json.loads(l) for l in open(p)] if os.path.exists(p) else []

seen = set()
for r in rows:
    u = r.get("url", "")
    if "clientError" not in u:
        continue
    q = urllib.parse.urlparse(u).query
    params = urllib.parse.parse_qs(q)
    raw = (params.get("r") or [""])[0]
    try:
        d = json.loads(raw)
    except Exception:
        d = {"_raw": raw}
    key = json.dumps(d, sort_keys=True)
    if key in seen:
        continue
    seen.add(key)
    print("=== clientError ===")
    for k, v in d.items():
        s = json.dumps(v) if not isinstance(v, str) else v
        print(f"  {k}: {s[:600]}")
    print()

if not seen:
    print("tidak ada clientError di log")

# Ringkas juga endpoint PX yang dipanggil, biar terlihat alur normalnya
print("=== endpoint PX yang dipanggil (unik) ===")
hosts = {}
for r in rows:
    u = r.get("url", "")
    if "hsprotect" in u or "perimeterx" in u:
        h = urllib.parse.urlparse(u).netloc + urllib.parse.urlparse(u).path
        hosts[h] = hosts.get(h, 0) + 1
for h, n in sorted(hosts.items(), key=lambda x: -x[1]):
    print(f"  {n:4}  {h}")
