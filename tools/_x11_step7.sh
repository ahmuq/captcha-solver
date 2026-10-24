#!/bin/bash
# Tahap 7: tekan-dan-tahan pada koordinat tombol yang benar, pantau progres.
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots
WID=2097155
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null; }

BX=638; BY=645
xdotool mousemove --sync $BX $BY; sleep 0.8
shot "20_hover"

xdotool mousedown 1
echo "  mousedown @ $BX,$BY"
for i in $(seq 1 14); do
  DX=$(( (RANDOM % 5) - 2 )); DY=$(( (RANDOM % 5) - 2 ))
  xdotool mousemove_relative -- "$DX" "$DY"
  sleep 0.5
done
shot "21_holding"
xdotool mouseup 1
echo "  mouseup setelah ~8s tahan"
sleep 4
shot "22_after_release"
echo "judul: $(xdotool getwindowname "$WID")"
sleep 12
shot "23_settled"
echo "judul: $(xdotool getwindowname "$WID")"
echo "=== selesai tahap 7 ==="
