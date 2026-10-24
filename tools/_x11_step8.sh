#!/bin/bash
# Tahap 8: tekan-dan-tahan pada tombol biru (552..767 x, 665..713 y) -> center (660,689).
# Pakai xdotool click --repeat? Tidak: hold manual + cek progres di tengah tahanan.
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots
WID=2097155
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window "$WID" "$SHOTDIR/$1.png" 2>/dev/null; }

BX=660; BY=689
xdotool mousemove --sync $BX $BY; sleep 1
shot "30_hover"

xdotool mousedown 1
echo "  mousedown @ $BX,$BY"
sleep 2
shot "31_hold_2s"
for i in $(seq 1 12); do
  DX=$(( (RANDOM % 5) - 2 )); DY=$(( (RANDOM % 5) - 2 ))
  xdotool mousemove_relative -- "$DX" "$DY"
  sleep 0.5
done
shot "32_hold_8s"
xdotool mouseup 1
echo "  mouseup"
sleep 4
shot "33_released"
echo "judul: $(xdotool getwindowname "$WID")"
sleep 14
shot "34_settled"
echo "judul: $(xdotool getwindowname "$WID")"
echo "=== selesai tahap 8 ==="
