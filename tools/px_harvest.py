#!/usr/bin/env python3
"""Satu sesi: walk + hold lewat X11 (tanpa protokol otomasi) -> panen cookie via CDP
dengan RELAUNCH profil yang sama.

Kenapa relaunch: tell protokol otomasi menghalangi *render* challenge PX, bukan
pembacaan cookie. Setelah gate selesai di jalur X11, cookie ada di store profil;
membuka ulang profil itu dengan --remote-debugging-port membuat browser sendiri yang
mendekripsi store-nya, jadi kita tidak perlu tahu kunci os_crypt kustom CloakBrowser
(dekripsi manual sudah dicoba dan gagal: bukan pbkdf2/peanuts).

Urutan operasi penting: cookie PX hanya ada di store setelah browser menutup store-nya,
jadi tutup dulu (SIGTERM) baru relaunch, jangan pkill -9.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

BIN = "/root/.cloakbrowser/chromium-154.0.8037.57.2-pro/chrome"
PORT = 9334
PX = ("_px3", "_pxvid", "_pxde", "pxcts", "_px2", "pxhd")


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def harvest(profile: str, port: int = PORT) -> dict:
    """Tutup browser pemilik profil dengan rapi, lalu baca cookie-nya via CDP."""
    # SIGTERM (bukan -9) supaya Chromium menulis store-nya ke disk
    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={profile}"], check=False)
    for _ in range(20):
        time.sleep(0.5)
        if not sh("pgrep", "-f", f"user-data-dir={profile}"):
            break
    else:
        subprocess.run(["pkill", "-9", "-f", f"user-data-dir={profile}"], check=False)
        time.sleep(1)

    subprocess.Popen([BIN, f"--user-data-dir={profile}", "--no-sandbox",
                      f"--remote-debugging-port={port}", "--remote-allow-origins=*",
                      "--no-first-run", "--no-default-browser-check",
                      "--window-size=900,600", "--window-position=0,0", "about:blank"],
                     stdout=open("/tmp/_harvest_cdp.log", "w"), stderr=subprocess.STDOUT,
                     env={**os.environ, "DISPLAY": ":99"})

    ver = None
    for _ in range(30):
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                        timeout=3) as r:
                ver = json.load(r)
                break
        except Exception:
            continue
    if not ver:
        return {"error": "CDP tidak siap"}

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
        targets = json.load(r)
    pages = [t for t in targets if t.get("type") == "page"]
    if not pages:
        return {"error": "tidak ada target page"}

    from websockets.sync.client import connect
    cookies = {}
    all_rows = []
    with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
        sock.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
        while True:
            msg = json.loads(sock.recv())
            if msg.get("id") == 1:
                all_rows = (msg.get("result") or {}).get("cookies", [])
                break
    for c in all_rows:
        if c["name"] in PX or "hsprotect" in c.get("domain", ""):
            cookies[c["name"]] = c["value"]

    subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={profile}"], check=False)
    return {"cookies": cookies, "total": len(all_rows), "browser": ver.get("Browser")}


def cookie_header(cookies: dict) -> str:
    order = ["pxcts", "_pxvid", "_px3", "_pxde"]
    parts = [f"{n}={cookies[n]}" for n in order if n in cookies]
    parts += [f"{n}={v}" for n, v in cookies.items() if n not in order]
    return "; ".join(parts)


if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "/tmp/x11fresh_profile"
    res = harvest(prof)
    if res.get("error"):
        print("gagal:", res["error"]); sys.exit(1)
    print(f"browser : {res['browser']}")
    print(f"total   : {res['total']} cookie di store")
    c = res["cookies"]
    print(f"PX      : {sorted(c)}")
    for n in sorted(c):
        print(f"  {n:8} len={len(c[n]):4} head={c[n][:24]!r}")
    hdr = cookie_header(c)
    print(f"header  : {len(hdr)} byte")
    json.dump(c, open("/tmp/px_cookies.json", "w"), indent=1)
    print("-> /tmp/px_cookies.json")
