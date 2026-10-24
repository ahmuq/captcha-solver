#!/bin/bash
# Tahap 6: tekan-dan-tahan gate PX lewat X11 (mouse asli, bukan CDP), lalu cek _px3.
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots
WID=2097155
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

# tombol "Press and hold" ~ (789, 617)
xdotool mousemove --sync 789 617; sleep 0.6
shot "17_hover_button"

# mouseDown -> tahan (biomekanik + PoW worker) -> mouseUp
xdotool mousedown 1
echo "  mousedown @789,617"
# micro-movement selama tahan (meniru biomekanik manusia)
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  DX=$(( (RANDOM % 5) - 2 )); DY=$(( (RANDOM % 5) - 2 ))
  xdotool mousemove_relative -- "$DX" "$DY"
  sleep 0.5
done
sleep 1
xdotool mouseup 1
echo "  mouseup (total tahan ~7s)"
sleep 5
shot "18_after_hold"

echo "judul: $(xdotool getwindowname "$WID")"
sleep 10
shot "19_settled"
echo "judul: $(xdotool getwindowname "$WID")"
echo "=== selesai tahap 6 ==="
