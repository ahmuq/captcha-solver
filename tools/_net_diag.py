#!/usr/bin/env python3
"""Uji: apakah event `failed` itu kegagalan JARINGAN, bukan vonis biomekanik?

Rekam semua aktivitas jaringan via CDP selama satu sesi solver penuh, termasuk target
iframe (auto-attach + flatten), lalu laporkan request yang gagal: status >= 400,
loadingFailed, atau blocked. Kalau ada endpoint PX yang gagal dimuat tepat sebelum
event `failed`, maka akarnya resource — bukan gerakan tangan.

Proxy dipakai supaya kondisinya sama dengan jalur produksi (proxy HP yang radio-nya
flapping).
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.browser import Browser                     # noqa: E402
from perimeterx.sessionless import (_Wrapper, _free_port,  # noqa: E402
                                    _find_gate_button)
from perimeterx.x11 import Hand                            # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
VID = sys.argv[1] if len(sys.argv) > 1 else "00000000-0000-4000-8000-000000000001"
UUID = sys.argv[2] if len(sys.argv) > 2 else "00000000-0000-4000-8000-000000000002"
SID = sys.argv[3] if len(sys.argv) > 3 else "00000000-0000-4000-8000-000000000003"


class CDP:
    """Koneksi CDP persisten yang mencatat SEMUA event (bukan sekali panggil)."""

    def __init__(self, ws):
        self.ws = ws
        self.n = 0
        self.replies = {}
        self.events = []
        self.lock = threading.Lock()
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        while True:
            try:
                m = json.loads(self.ws.recv())
            except Exception:
                return
            with self.lock:
                if "id" in m:
                    self.replies[m["id"]] = m
                else:
                    self.events.append(m)

    def send(self, method, params=None, session=None, timeout=30):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        self.ws.send(json.dumps(msg))
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lock:
                if self.n in self.replies:
                    return self.replies.pop(self.n)
            time.sleep(0.02)
        return None

    def drain(self):
        with self.lock:
            evs, self.events = self.events, []
            return evs


def main():
    port = _free_port()
    profile = f"/tmp/_net_{int(time.time())}"
    br = Browser(profile, proxy=PROXY, width=1280, height=900)
    challenge = f"https://iframe.hsprotect.net/index.html?app_id={APP}&session_id={SID}"
    wrap = _Wrapper(challenge, UUID, VID)
    print(f"wrapper : {wrap.url}")
    print(f"proxy   : {PROXY.split('@')[-1]}")

    from websockets.sync.client import connect
    failed_reqs, all_reqs, load_failed = [], [], []
    try:
        br.start_cdp(port)
        if not getattr(br, "cdp_ws", None):
            print("CDP tidak naik"); return
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version",
                                    timeout=5) as r:
            bws = json.load(r)["webSocketDebuggerUrl"]

        with connect(bws, max_size=100 * 1024 * 1024) as sock:
            c = CDP(sock)
            c.send("Target.setAutoAttach",
                   {"autoAttach": True, "waitForDebuggerOnStart": False,
                    "flatten": True})
            tg = c.send("Target.getTargets") or {}
            page = [t for t in (tg.get("result") or {}).get("targetInfos", [])
                    if t.get("type") == "page"]
            if not page:
                print("tidak ada target page"); return
            at = c.send("Target.attachToTarget",
                        {"targetId": page[0]["targetId"], "flatten": True})
            sid = (at.get("result") or {}).get("sessionId")
            print(f"sesi CDP: {sid[:12]}...")
            for m in ("Network.enable", "Page.enable"):
                c.send(m, {}, session=sid)

            c.send("Page.navigate", {"url": wrap.url}, session=sid)

            # Beri sesi berjalan: render -> hold -> vonis PX
            t0 = time.time()
            while time.time() - t0 < 35 and not wrap.rendered.is_set():
                time.sleep(1)
            print(f"gate render: {wrap.rendered.is_set()}")

            wid = br.window_id()
            box = _find_gate_button(br, wid, br.height) if wid else None
            bx, by = box or (br.width // 2, 190)
            print(f"tombol: ({bx},{by})")
            hand = Hand()
            hand.press_and_hold(9.0, bx, by, print)

            t0 = time.time()
            while time.time() - t0 < 40:
                if wrap.solved.is_set() or wrap.failed.is_set():
                    break
                time.sleep(0.5)
            print(f"vonis PX: solved={wrap.solved.is_set()} failed={wrap.failed.is_set()}")
            time.sleep(3)

            # Kumpulkan event jaringan
            for ev in c.drain():
                m = ev.get("method")
                p = ev.get("params") or {}
                if m == "Network.requestWillBeSent":
                    all_reqs.append(p.get("request", {}).get("url", ""))
                elif m == "Network.responseReceived":
                    st = (p.get("response") or {}).get("status")
                    url = (p.get("response") or {}).get("url", "")
                    if st and st >= 400:
                        failed_reqs.append((st, url))
                elif m == "Network.loadingFailed":
                    load_failed.append((p.get("errorText"), p.get("type"),
                                        p.get("blockedReason")))
    finally:
        wrap.close()
        br.stop()
        subprocess.run(["rm", "-rf", profile], check=False)

    print(f"\n=== TOTAL REQUEST: {len(all_reqs)} ===")
    px = [u for u in all_reqs if "hsprotect" in u or "perimeterx" in u or "px" in u]
    for u in all_reqs:
        tag = "PX" if ("hsprotect" in u or "perimeterx" in u) else "  "
        print(f"  [{tag}] {u[:150]}")
    print(f"\n=== RESPONS GAGAL (status >= 400): {len(failed_reqs)} ===")
    for st, u in failed_reqs:
        print(f"  {st}  {u[:150]}")
    print(f"\n=== LOADING FAILED: {len(load_failed)} ===")
    for err, typ, blocked in load_failed:
        print(f"  {err}  type={typ}  blocked={blocked}")


main()
