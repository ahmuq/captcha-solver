#!/bin/bash
# Uji lengkap: --password-store=basic + tunggu flush -> dekripsi dengan "peanuts".
set -u
BIN=/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome
P=/tmp/cryptotest3
export DISPLAY=:99

pkill -f "user-data-dir=/tmp/cryptotest" 2>/dev/null; sleep 2
rm -rf "$P"; mkdir -p "$P"

"$BIN" --user-data-dir="$P" --no-sandbox \
  --password-store=basic \
  --no-first-run --no-default-browser-check \
  --window-size=1000,700 --window-position=0,0 \
  "https://www.wikipedia.org" > /tmp/cryptotest3.log 2>&1 &
PID=$!
echo "pid=$PID, tunggu 65s supaya cookie ter-flush ke disk"
sleep 65

.venv/bin/python - <<'EOF'
import hashlib, shutil, sqlite3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

shutil.copy2("/tmp/cryptotest3/Default/Cookies", "/tmp/_c3.db")
con = sqlite3.connect("/tmp/_c3.db")
rows = con.execute("select name,host_key,encrypted_value from cookies").fetchall()
con.close()
print("baris cookie:", len(rows))

def dec(blob, key):
    if not blob.startswith(b"v10"):
        return blob.decode("utf-8","ignore") if blob else None
    body = blob[3:]
    if len(body) < 28: return None
    try: pt = AESGCM(key).decrypt(body[:12], body[12:], None)
    except Exception: return None
    if len(pt) > 32: pt = pt[32:]
    return pt.decode("utf-8","ignore")

for pw in ("peanuts","","chrome"):
    for iters in (1,1003):
        key = hashlib.pbkdf2_hmac("sha1", pw.encode(), b"saltysalt", iters, dklen=16)
        hits = [(n,h,dec(e or b"",key)) for n,h,e in rows]
        good = [x for x in hits if x[2] and len(x[2])>=3]
        if good:
            print(f"COCOK pw={pw!r} iters={iters} -> {len(good)}/{len(rows)} terbaca")
            for n,h,v in good[:4]:
                print(f"   {n:16} {h:22} {v[:20]!r}")
            raise SystemExit(0)
print("tidak ada kombinasi yang cocok")
EOF
pkill -f "user-data-dir=$P" 2>/dev/null
