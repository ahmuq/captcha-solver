#!/usr/bin/env python3
"""Rotasi sampai dapat IP ber-prefix BARU, lalu uji walk+hold dengan hand 100 Hz.

Prefix IP HP yang sudah dipakai hari ini (dan jenuh): 140.213.34, 140.213.36,
140.213.19, 140.213.17, 140.213.71, 112.215.149. Pool Telkomsel punya beberapa
prefix; sesi yang masih "bersih" kemungkinan ada di prefix yang belum tersentuh.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _hloop
from _hloop_walk import walk, hold

USED = ("140.213.34", "140.213.36", "140.213.19", "140.213.17",
        "140.213.71", "112.215.149")
PROXY = _hloop.PROXY


def egress():
    return _hloop.run("curl", "-s", "--max-time", "25", "-x", PROXY,
                      "https://api.ipify.org")


def rotate():
    _hloop.run("curl", "-s", "--max-time", "40",
               "http://178.83.181.16:18081/rotate?token=capok123")
    for _ in range(10):
        time.sleep(6)
        ip = egress()
        if ip:
            return ip
    return ""


found = None
for i in range(10):
    ip = rotate()
    fresh = bool(ip) and not any(ip.startswith(p) for p in USED)
    _hloop.log(f"rotasi {i+1}: {ip or '(kosong)'}{'  <-- PREFIX BARU' if fresh else ''}")
    if fresh:
        found = ip
        break
    time.sleep(8)

if not found:
    _hloop.log("tidak dapat IP prefix baru; pakai IP terakhir")
    found = egress()

_hloop.log(f"IP yang akan dipakai: {found}")
_hloop.log("jeda 90s supaya radio proxy stabil")
time.sleep(90)

WID = _hloop.launch()
_hloop.log(f"WID: {WID} | {_hloop.run('xdotool', 'getwindowname', WID)}")
t = walk(WID, "newip")
_hloop.log(f"hasil submit: {t}")
if "prove" in t.lower():
    t = hold(WID, "newip")
    _hloop.log(">>> LOLOS" if "prove" not in t.lower() else ">>> masih di gate")
else:
    _hloop.log(f">>> tidak ada gate: {t}")
