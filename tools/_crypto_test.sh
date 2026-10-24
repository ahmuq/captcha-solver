#!/bin/bash
# Uji: apakah --password-store=basic membuat cookie store bisa didekripsi dengan
# password "peanuts" (default Chromium Linux tanpa keyring)?
# Pakai situs NON-Microsoft supaya tidak membakar sesi signup.
set -u
BIN=/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome
P=/tmp/cryptotest
export DISPLAY=:99

pkill -f "user-data-dir=$P" 2>/dev/null; sleep 2
rm -rf "$P"; mkdir -p "$P"

"$BIN" --user-data-dir="$P" --no-sandbox \
  --password-store=basic \
  --no-first-run --no-default-browser-check \
  --window-size=1000,700 --window-position=0,0 \
  "https://github.com" > /tmp/cryptotest.log 2>&1 &
echo "pid=$!"
sleep 15
pkill -f "user-data-dir=$P" 2>/dev/null
sleep 3
echo "=== cookie store ==="
ls -la "$P/Default/Cookies" 2>/dev/null || echo "tidak ada store"
echo "=== os_crypt di Local State ==="
python3 -c "
import json
try:
    s=json.load(open('$P/Local State'))
    oc=s.get('os_crypt',{})
    print('os_crypt keys:', list(oc.keys()))
    ek=oc.get('encrypted_key')
    print('encrypted_key:', (ek[:24]+'...') if ek else None)
except Exception as e: print('err', e)
"
