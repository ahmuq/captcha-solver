#!/usr/bin/env python3
"""Diagnose a CloakBrowser license key without ever printing the key itself."""
import json
import os
import sys
import urllib.request

KEY = os.environ.get("CBKEY", "")
if not KEY:
    sys.exit("CBKEY not set")

REDACT = lambda s: (s or "").replace(KEY, "<KEY>")


def probe(url, payload=None, method="GET"):
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {KEY}")
    req.add_header("User-Agent", "cloakbrowser-diagnose/1.0")
    data = json.dumps(payload).encode() if payload else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=25) as r:
            return r.status, REDACT(r.read().decode(errors="replace"))[:800]
    except urllib.error.HTTPError as e:
        return e.code, REDACT(e.read().decode(errors="replace"))[:800]
    except Exception as e:
        return 0, REDACT(str(e))[:300]


BASE = "https://cloakbrowser.dev"
print("key shape :", f"{len(KEY)} chars, prefix={KEY[:3]!r}")
print()

print("=== GET /api/license/validate (bearer) ===")
s, b = probe(f"{BASE}/api/license/validate")
print("HTTP", s)
print(b)
print()

print("=== POST /api/license/validate {'license_key': ...} ===")
s, b = probe(f"{BASE}/api/license/validate", {"license_key": KEY}, "POST")
print("HTTP", s)
print(b)
print()

print("=== GET /api/license/validate?license_key=... ===")
s, b = probe(f"{BASE}/api/license/validate?license_key={KEY}")
print("HTTP", s)
print(b)
print()

print("=== GET /api/license/session/count ===")
s, b = probe(f"{BASE}/api/license/session/count")
print("HTTP", s)
print(b)