#!/bin/bash
# Tahap 4: isi nama, submit, lalu periksa apakah gate PX naik (atau diblokir).
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots

WID=$(xdotool search --name "Add your name" | tail -1)
if [ -z "$WID" ]; then WID=$(xdotool search --name "Chromium" | tail -1); fi
echo "window: ${WID:-TIDAK KETEMU}"
[ -z "$WID" ] && exit 1
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

shot "9_name_step"
# klik field nama depan (perkiraan tengah kartu) lalu isi
xdotool mousemove --sync 639 470 click 1; sleep 1
xdotool type --window "$WID" --delay 70 "Nathan"
sleep 0.6
xdotool key --window "$WID" Tab; sleep 0.6
xdotool type --window "$WID" --delay 70 "Kusumo"
sleep 1
shot "10_name_filled"

# submit -> di sinilah gate PX / blokir muncul
xdotool key --window "$WID" Return
sleep 8
shot "11_after_submit"
echo "judul: $(xdotool getwindowname "$WID")"

# tunggu kalau gate perlu waktu render
sleep 12
shot "12_gate_wait"
echo "judul: $(xdotool getwindowname "$WID")"
echo "=== selesai tahap 4 ==="
