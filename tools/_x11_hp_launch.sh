#!/bin/bash
# Jalankan CloakBrowser X11 lewat proxy HP (IP residensial), buka form signup.
set -u
source /tmp/_pxproxy.env
BIN=/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome
PROFILE=/tmp/x11hp
export DISPLAY=:99

# matikan browser X11 sebelumnya
pkill -f "user-data-dir=/tmp/x11walk" 2>/dev/null
sleep 2
rm -rf "$PROFILE"; mkdir -p "$PROFILE"

"$BIN" \
  --user-data-dir="$PROFILE" \
  --no-sandbox \
  --proxy-server="$PXPROXY" \
  --fingerprint=424242 \
  --fingerprint-platform=windows \
  --window-size=1280,900 --window-position=0,0 \
  --no-first-run --no-default-browser-check \
  "https://signup.live.com/signup?lic=1" \
  > /tmp/x11hp.log 2>&1 &
echo "chrome pid=$!"
sleep 16

echo "=== window ==="
for w in $(xdotool search --name ""); do t=$(xdotool getwindowname $w 2>/dev/null); [ -n "$t" ] && echo "$w | $t"; done | head -5
echo "=== egress browser (cek via halaman) ==="
import -window root /tmp/x11shots/HP0_open.png 2>/dev/null && echo "shot ok"
