#!/bin/bash
# Tahap 2: jalankan form signup lewat X11 (xdotool) pada browser yang sudah berjalan
# tanpa protokol otomasi. Screenshot tiap step supaya bisa diperiksa visual.
set -u
export DISPLAY=:99

EMAIL="x11probe$RANDOM@outlook.com"
PW='Zx9kLmQ2vRt7pW!4'
SHOTDIR=/tmp/x11shots
mkdir -p "$SHOTDIR"

WID=$(xdotool search --name "Microsoft account" | tail -1)
if [ -z "$WID" ]; then WID=$(xdotool search --name "Chromium" | tail -1); fi
echo "window: ${WID:-TIDAK KETEMU}"
[ -z "$WID" ] && exit 1

xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1

shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

echo "EMAIL=$EMAIL" > /tmp/x11walk.state

# --- step 1: email ---
xdotool type --window "$WID" --delay 60 "$EMAIL"
sleep 1
shot "1_email_typed"
xdotool key --window "$WID" Return
sleep 6
shot "2_after_email"

# --- step 2: password ---
xdotool type --window "$WID" --delay 60 "$PW"
sleep 1
shot "3_password_typed"
xdotool key --window "$WID" Return
sleep 6
shot "4_after_password"

echo "=== state setelah email+password ==="
xdotool getwindowname "$WID"
echo "=== selesai tahap 2 ==="
