#!/bin/bash
# Tahap 3: isi birthdate + nama lewat X11, lalu lihat apakah gate PX naik.
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots

WID=$(xdotool search --name "Add some details" | tail -1)
if [ -z "$WID" ]; then WID=$(xdotool search --name "Microsoft account" | tail -1); fi
echo "window: ${WID:-TIDAK KETEMU}"
[ -z "$WID" ] && exit 1
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

# koordinat relatif jendela (window di 0,0 dan berukuran 1280x900)
click() { xdotool mousemove --sync "$1" "$2" click 1; sleep "${3:-1}"; }

# --- Month: klik dropdown, pilih opsi (klik opsi lalu Enter) ---
click 513 538 1
shot "5_month_open"
xdotool key --window "$WID" Down; sleep 0.4
xdotool key --window "$WID" Down; sleep 0.4
xdotool key --window "$WID" Return; sleep 1
shot "6_month_set"

# --- Day ---
click 638 538 1
xdotool key --window "$WID" Down; sleep 0.4
xdotool key --window "$WID" Down; sleep 0.4
xdotool key --window "$WID" Return; sleep 1

# --- Year ---
click 763 538 1
xdotool type --window "$WID" --delay 70 "1995"
sleep 1
shot "7_birthdate_set"

# --- Next ---
click 639 712 2
sleep 7
shot "8_after_birthdate"
echo "judul sekarang: $(xdotool getwindowname "$WID")"

echo "=== selesai tahap 3 ==="
