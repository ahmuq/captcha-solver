"""Seed the CALLER's PX visitor id into a profile before the challenge opens.

Why this exists
---------------
The challenge page resolves its visitor id like this (read from its inline script):

    function v(){ var t = u("_pxvid") || x(); t && (window._pxVid = t) }
    function x(){ var t = localStorage.getItem(window._pxAppId + "_pxvid");
                  return t ? JSON.parse(atob(t)).val : null }
    captcha: `${appId}/captcha.js?a=c&m=0&u=${window._pxUuid}&v=${window._pxVid}`

The cookie is checked FIRST, and PX's own ``_pxvid`` is httpOnly — so writing it from
page JS (``document.cookie``) cannot override it. It must be set through CDP
``Network.setCookie``, which can also write httpOnly cookies and replaces an existing
cookie with the same name/domain/path.

Why it matters: without this the browser carries a visitor of PX's own, so the minted
``_px3`` belongs to a different visitor than the challenge the caller verifies.
Measured symptom: the solve reports success locally (``gate_reached=true``, ``_px3``
harvested) while the caller's ``risk/verify`` keeps answering
``state=riskChallengeRequired``.

Mechanics
---------
Two launches, in order:

1. this module — a CDP launch used ONLY to seed the cookie + localStorage;
2. the solve — a launch **without** ``--remote-debugging-*``, because that flag alone
   stops the gate from rendering.

The profile is closed with SIGTERM in between so Chromium flushes state to disk.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import time
import urllib.request

from .x11 import browser_binary

log = logging.getLogger(__name__)

ORIGIN = "https://iframe.hsprotect.net/index.html"
COOKIE_DOMAIN = ".hsprotect.net"


def _free_port() -> int:
    """Port TCP kosong — CDP sebelumnya bisa gagal naik kalau port masih terpakai."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _kill_profile(profile: str) -> None:
    subprocess.run(["pkill", "-9", "-f", f"user-data-dir={profile}"], check=False)
    time.sleep(0.5)


def _wait_pages(port: int, timeout: float) -> list:
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(1)
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list",
                                        timeout=3) as r:
                pages = [t for t in json.load(r) if t.get("type") == "page"]
            if pages:
                return pages
        except Exception:
            continue
    return []


def seed_visitor(profile: str, app_id: str, vid: str, proxy: str = None,
                 port: int = None, timeout: float = 45.0) -> dict:
    """Write ``vid`` into the profile as cookie ``_pxvid`` + localStorage ``<appId>_pxvid``.

    Returns a report: whether each store took the value, and the UA of this launch (the
    caller must replay with the same UA, which ``_px3`` is bound to as well).
    """
    if not vid:
        return {"seeded": False, "error": "vid empty"}

    if port is None:
        port = _free_port()
    _kill_profile(profile)          # pastikan tidak ada sisa instance di profil ini
    args = [browser_binary(), f"--user-data-dir={profile}", "--no-sandbox",
            f"--remote-debugging-port={port}", "--remote-allow-origins=*",
            "--no-first-run", "--no-default-browser-check",
            "--window-size=1280,900", "--window-position=0,0", ORIGIN]
    if proxy:
        args.insert(3, f"--proxy-server={proxy}")

    proc = subprocess.Popen(args, stdout=open("/tmp/px_seed.log", "w"),
                            stderr=subprocess.STDOUT,
                            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":99")})
    report = {"seeded": False}
    try:
        pages = _wait_pages(port, timeout)
        if not pages:
            return {"seeded": False, "error": "CDP target never appeared"}
        time.sleep(5)          # let PX set its own cookies first, so ours replaces them

        from websockets.sync.client import connect
        payload = base64.b64encode(json.dumps({"val": vid}).encode()).decode()
        with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
            cid = 0

            def call(method, params):
                nonlocal cid
                cid += 1
                sock.send(json.dumps({"id": cid, "method": method, "params": params}))
                while True:
                    m = json.loads(sock.recv())
                    if m.get("id") == cid:
                        return m

            # Cookie lewat CDP: satu-satunya cara menimpa _pxvid httpOnly milik PX.
            res = call("Network.setCookie", {
                "name": "_pxvid", "value": vid, "domain": COOKIE_DOMAIN, "path": "/",
                "secure": True, "httpOnly": True, "sameSite": "None",
                "expires": time.time() + 86400})
            report["cookie"] = bool((res.get("result") or {}).get("success"))

            # Verifikasi IN-MEMORY: setCookie bisa melaporkan sukses tanpa nilai benar-
            # benar terpasang (mis. domain tidak cocok dengan dokumen).
            res = call("Network.getCookies", {"urls": [ORIGIN]})
            got = {c["name"]: c.get("value")
                   for c in ((res.get("result") or {}).get("cookies") or [])}
            report["in_memory_pxvid"] = got.get("_pxvid")
            report["cookie"] = report["in_memory_pxvid"] == vid

            # localStorage juga diisi: skrip challenge memakai cookie ATAU localStorage.
            ls_key = json.dumps(app_id + "_pxvid")
            res = call("Runtime.evaluate", {
                "expression": (f"localStorage.setItem({ls_key}, {json.dumps(payload)});"
                               f"localStorage.getItem({ls_key})"),
                "returnByValue": True})
            report["localstorage"] = bool(
                ((res.get("result") or {}).get("result") or {}).get("value"))

            res = call("Runtime.evaluate", {
                "expression": "document.cookie.indexOf('_pxvid=') >= 0 ? 'yes' : 'no'",
                "returnByValue": True})
            report["cookie_visible_to_js"] = (
                ((res.get("result") or {}).get("result") or {}).get("value") == "yes")

            res = call("Runtime.evaluate", {
                "expression": "navigator.userAgent", "returnByValue": True})
            report["user_agent"] = (
                ((res.get("result") or {}).get("result") or {}).get("value") or "")

        report["seeded"] = bool(report.get("cookie") or report.get("localstorage"))
        log.info("seed: cookie=%s localStorage=%s ua=%s", report.get("cookie"),
                 report.get("localstorage"), (report.get("user_agent") or "")[:45])
    except Exception as e:                                          # noqa: BLE001
        report["error"] = str(e)
        log.warning("seed visitor failed: %s", e)
    finally:
        # SIGTERM supaya Chromium menulis cookie + localStorage ke disk. Chromium
        # meng-flush store berkala (~30 s), bukan tepat saat shutdown — diukur: setelah
        # SIGTERM store masih kosong, dan baru terisi setelah ditunggu. Jadi kita
        # tunggu sampai nilainya benar-benar ada di disk sebelum lanjut ke sesi solve.
        subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={profile}"], check=False)
        try:
            proc.wait(timeout=15)
        except Exception:
            subprocess.run(["pkill", "-9", "-f", f"user-data-dir={profile}"], check=False)
        report["persisted"] = _wait_persisted(profile, vid, timeout=70.0)
        log.info("seed persist=%s (cookie=%s ls=%s)", report.get("persisted"),
                 report.get("cookie"), report.get("localstorage"))
    return report


def _wait_persisted(profile: str, vid: str, timeout: float = 70.0) -> bool:
    """Tunggu sampai ``vid`` benar-benar tertulis di store cookie di disk."""
    import sqlite3
    store = os.path.join(profile, "Default", "Cookies")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(store):
            try:
                con = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
                n = list(con.execute(
                    "SELECT COUNT(*) FROM cookies WHERE name = '_pxvid'"))
                con.close()
                if n and n[0][0]:
                    return True
            except Exception:
                pass
        time.sleep(3)
    return False
