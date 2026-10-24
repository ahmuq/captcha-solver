#!/bin/bash
# Uji ulang dengan situs yang pasti menyetel cookie + tunggu lebih lama.
set -u
BIN=/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome
P=/tmp/cryptotest2
export DISPLAY=:99

pkill -f "user-data-dir=/tmp/cryptotest" 2>/dev/null; sleep 2
rm -rf "$P"; mkdir -p "$P"

"$BIN" --user-data-dir="$P" --no-sandbox \
  --password-store=basic \
  --no-first-run --no-default-browser-check \
  --window-size=1000,700 --window-position=0,0 \
  "https://www.wikipedia.org" > /tmp/cryptotest2.log 2>&1 &
echo "pid=$!"
sleep 20
# buka situs kedua untuk memastikan ada cookie
export DISPLAY=:99
xdotool search --name "Wikipedia" | tail -1 > /tmp/_w 2>/dev/null
python3 - <<'EOF'
import json, os, sqlite3, shutil
p="/tmp/cryptotest2/Default/Cookies"
print("store ada:", os.path.exists(p))
if os.path.exists(p):
    shutil.copy2(p, "/tmp/_c2.db")
    con=sqlite3.connect("/tmp/_c2.db")
    n=con.execute("select count(*) from cookies").fetchone()[0]
    print("baris:", n)
    for r in con.execute("select name,host_key,length(encrypted_value) from cookies limit 5"):
        print("  ", r)
s=json.load(open("/tmp/cryptotest2/Local State"))
print("os_crypt:", list(s.get("os_crypt",{}).keys()))
EOF
pkill -f "user-data-dir=$P" 2>/dev/null
