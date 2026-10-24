#!/bin/bash
# Tahap 5: isi nama dengan koordinat benar, submit, dan tangkap apa yang muncul
# (gate PX press-hold, atau blokir Microsoft).
set -u
export DISPLAY=:99
SHOTDIR=/tmp/x11shots
WID=2097155
xdotool windowactivate --sync "$WID" 2>/dev/null || xdotool windowfocus "$WID"
sleep 1
shot() { import -window root "$SHOTDIR/$1.png" 2>/dev/null && echo "  shot: $1"; }

# First name (490..815 x, 415..450 y) -> center ~ (650, 432)
xdotool mousemove --sync 650 432 click 1; sleep 1
xdotool type --window "$WID" --delay 70 "Nathan"
sleep 1
# Last name -> center ~ (650, 512)
xdotool mousemove --sync 650 512 click 1; sleep 1
xdotool type --window "$WID" --delay 70 "Kusumo"
sleep 1
shot "14_name_filled"

# Next -> gate PX / blokir muncul di sini
xdotool mousemove --sync 650 722 click 1
sleep 10
shot "15_after_name_submit"
echo "judul: $(xdotool getwindowname "$WID")"

# gate PX butuh waktu render
sleep 15
shot "16_gate_settled"
echo "judul: $(xdotool getwindowname "$WID")"
echo "=== selesai tahap 5 ==="
