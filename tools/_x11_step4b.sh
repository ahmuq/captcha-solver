#!/bin/bash
# Tahap 4b: Next dari details -> isi nama -> submit -> cek gate PX.
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots
WID=2097155
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

# Next dari step details
xdotool mousemove --sync 640 710 click 1; sleep 7
shot "13_name_step"
TITLE=$(xdotool getwindowname "$WID")
echo "judul setelah Next: $TITLE"

# ambil koordinat field nama dari window-shot supaya tidak menebak
import -window "$WID" "$SHOTDIR/win_name.png" 2>/dev/null
echo "window-shot: $SHOTDIR/win_name.png"

echo "=== selesai tahap 4b ==="
