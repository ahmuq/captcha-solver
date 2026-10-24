#!/bin/bash
# Eksperimen: jalankan CloakBrowser Pro TANPA protokol otomasi apa pun (tanpa
# --remote-debugging-*), kendalikan form lewat X11 (xdotool), lalu periksa apakah
# gate PX naik dan _px3 terbit — pembanding terhadap jalur Playwright/CDP.
set -u
BIN=/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome
PROFILE=/tmp/x11walk
SHOT=/tmp/x11walk.png
DISPLAY=:99

rm -rf "$PROFILE"; mkdir -p "$PROFILE"

# tanpa remote-debugging-pipe/port: tidak ada permukaan protokol otomasi
DISPLAY=$DISPLAY "$BIN" \
  --user-data-dir="$PROFILE" \
  --no-sandbox \
  --fingerprint=424242 \
  --fingerprint-platform=windows \
  --window-size=1280,900 \
  --window-position=0,0 \
  --no-first-run --no-default-browser-check \
  --disable-features=Translate \
  "https://signup.live.com/signup?lic=1" \
  > /tmp/x11walk.log 2>&1 &
CHROME_PID=$!
echo "chrome pid=$CHROME_PID"
sleep 14

export DISPLAY
echo "=== jendela yang ada ==="
xdotool search --name "." getwindowname %@ 2>/dev/null | head -5

import -window root "$SHOT" 2>/dev/null && echo "screenshot: $SHOT"

echo "=== ukuran jendela chrome ==="
WID=$(xdotool search --class -- "chrome" 2>/dev/null | tail -1)
echo "window id: ${WID:-tidak ketemu}"
[ -n "${WID:-}" ] && xdotool getwindowgeometry "$WID"

echo "PID=$CHROME_PID" > /tmp/x11walk.pid
echo "WID=${WID:-}" >> /tmp/x11walk.pid
echo "=== selesai tahap 1 ==="
