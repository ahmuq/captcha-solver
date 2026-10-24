"""Launch CloakBrowser directly (no automation protocol) and harvest its cookies.

Two facts drive this module:

1. The browser must be launched **without** ``--remote-debugging-*`` — that flag alone
   stops PerimeterX from rendering the gate. So Playwright cannot be used here, and
   the profile's cookie store must be read another way.

2. The store's ``encrypted_value`` is **not** decryptable with standard Chromium
   parameters on this build. Measured: the blob is real AES-256-GCM (``v10`` prefix,
   12-byte nonce + 16-byte tag; ``_px3`` = 3 + 12 + 644 + 16 = 675 bytes), but no
   password/salt/iteration/keylength combination produced plaintext — ``peanuts`` plus
   ~400k short strings from the binary, salts ``saltysalt``/``salt``/``cloakbrowser``/…,
   iterations 1/1003/1004/1005/1007/1008/1009/1013, key lengths 16 and 32. ``Local
   State`` has an ``os_crypt`` object with no ``encrypted_key``.

   Working method: let the browser decrypt its own store. Close it with **SIGTERM**
   (Chromium only flushes the cookie store on a clean shutdown — ``kill -9`` leaves a
   stale store), then relaunch the same profile with ``--remote-debugging-port`` and
   read ``Storage.getCookies``. The automation protocol is harmless here because the
   challenge is already finished.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
import urllib.request

from .x11 import browser_binary, _run

log = logging.getLogger(__name__)

PX_COOKIE_NAMES = ("_px3", "_pxvid", "_pxde", "pxcts", "_px2", "pxhd")


class Browser:
    """A CloakBrowser instance driven over X11 (no automation protocol)."""

    def __init__(self, profile: str, proxy: str = None, width: int = 1280,
                 height: int = 900):
        self.profile = profile
        self.proxy = proxy
        self.width, self.height = width, height
        self.proc = None
        self.pid = None

    # ---------- lifecycle ----------
    def start(self, url: str, wait: float = 17.0) -> None:
        os.makedirs(self.profile, exist_ok=True)
        args = [
            browser_binary(),
            f"--user-data-dir={self.profile}",
            "--no-sandbox",
            "--fingerprint=%d" % random.randint(100000, 999999),
            *self._platform_args(),
            f"--window-size={self.width},{self.height}",
            "--window-position=0,0",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
        if self.proxy:
            args.insert(3, f"--proxy-server={self.proxy}")
        env = {**os.environ}
        env.setdefault("DISPLAY", ":99")
        self.log = open(f"/tmp/px_x11_{os.path.basename(self.profile)}.log", "w")
        self.proc = subprocess.Popen(args, stdout=self.log, stderr=subprocess.STDOUT,
                                     env=env)
        self.pid = self.proc.pid
        self.wait_window(wait)

    def wait_window(self, base_wait: float = 17.0, timeout: float = 110.0) -> str | None:
        """Tunggu sampai window UTAMA browser benar-benar ter-map.

        ``time.sleep(17)`` saja tidak cukup, dan itu akar dari seluruh masalah
        deteksi: pada detik ke-17 yang sudah ada hanya window bantu berukuran
        10x10 (``chrome`` / ``Chromium clipboard``) yang **tidak bisa** di-capture,
        sedangkan window asli 1280x900 berjudul "<url> - Chromium" baru muncul
        sekitar detik ke-60. Akibatnya ``window_id`` mengembalikan id yang salah
        atau None, semua deteksi berbasis screenshot gagal diam-diam, dan solver
        berjalan dengan koordinat tebak.

        Kriterianya ukuran, bukan judul: window asli selalu jauh lebih besar
        daripada window bantu (1280x900 vs 10x10).
        """
        time.sleep(base_wait)
        t0 = time.time()
        while time.time() - t0 < timeout:
            for w in self._window_candidates():
                m = re.search(r"Geometry: (\d+)x(\d+)",
                              _run("xdotool", "getwindowgeometry", w))
                if not m:
                    continue
                if int(m.group(1)) < 600 or int(m.group(2)) < 400:
                    continue                    # window bantu, bukan halaman
                test = f"/tmp/_capw_{os.getpid()}.png"
                try:
                    r = subprocess.run(["import", "-window", w, test],
                                       capture_output=True, timeout=25)
                except Exception:                                     # noqa: BLE001
                    continue
                if r.returncode == 0 and os.path.exists(test) \
                        and os.path.getsize(test) > 5000:
                    log.info("window utama siap: %s setelah %.0f detik",
                             w, base_wait + (time.time() - t0))
                    return w
            time.sleep(2.0)
        log.warning("window utama tidak muncul dalam %.0f detik", base_wait + timeout)
        return None

    def _window_candidates(self) -> list[str]:
        out = []
        for args in (("--onlyvisible", "--name", "."), ("--name", "")):
            got = _run("xdotool", "search", *args)
            out += [w for w in got.splitlines() if w.strip()]
        return list(dict.fromkeys(out))

    # ---------- CDP variant ----------
    # Terukur: protokol otomasi SENDIRI tidak mematikan gate — yang mematikannya adalah
    # tidak adanya parent yang mengirim postMessage (uji lama memakai Playwright yang
    # mengendalikan lewat CDP TANPA wrapper, jadi dua variabel tercampur). Dengan wrapper
    # parent, gate tetap render meski CDP aktif. Itu membuka dua hal yang tidak mungkin
    # di jalur tanpa CDP: menanam `_pxvid` in-memory (setCookie) lalu langsung memakainya
    # di sesi yang sama, dan membaca cookie tanpa relaunch.
    def start_cdp(self, port: int, url: str = "about:blank", wait: float = 12.0) -> None:
        os.makedirs(self.profile, exist_ok=True)
        self.cdp_port = port
        args = [
            browser_binary(),
            f"--user-data-dir={self.profile}",
            "--no-sandbox",
            f"--fingerprint=%d" % random.randint(100000, 999999),
            *self._platform_args(),
            f"--window-size={self.width},{self.height}",
            "--window-position=0,0",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ]
        if self.proxy:
            args.insert(3, f"--proxy-server={self.proxy}")
        env = {**os.environ}
        env.setdefault("DISPLAY", ":99")
        self.log = open(f"/tmp/px_cdp_{os.path.basename(self.profile)}.log", "w")
        self.proc = subprocess.Popen(args, stdout=self.log, stderr=subprocess.STDOUT,
                                     env=env)
        self.pid = self.proc.pid
        self._wait_cdp(wait)

    def _platform_args(self) -> list:
        """Flag platform fingerprint, bisa dikonfigurasi untuk uji A/B.

        PX memvalidasi konsistensi fingerprint, dan `captchaNotRendered` muncul saat
        teks challenge gagal digambar. Terukur di mesin ini: fc-match "Segoe UI" ->
        "Nimbus Sans L" dan "Arial" -> "Liberation Sans", artinya browser yang mengaku
        Windows menggambar dengan font Linux — kontradiksi yang bisa dibaca PX.
        Set PX_PLATFORM=linux untuk menguji tanpa klaim platform Windows.
        """
        plat = os.environ.get("PX_PLATFORM", "windows").strip().lower()
        return [f"--fingerprint-platform={plat}"] if plat and plat != "none" else []

    def _wait_cdp(self, timeout: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(1)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{self.cdp_port}/json/list", timeout=3) as r:
                    pages = [t for t in json.load(r) if t.get("type") == "page"]
                if pages:
                    self.cdp_ws = pages[0]["webSocketDebuggerUrl"]
                    return True
            except Exception:
                continue
        return False

    def start_netlog(self, path: str = "/tmp/px_net.jsonl") -> None:
        """Catat aktivitas jaringan via CDP ke file (diagnostik, opt-in).

        Dipakai untuk memisahkan penolakan biomekanik dari kegagalan resource: kalau ada
        endpoint PX yang gagal dimuat tepat sebelum event `failed`, akarnya jaringan,
        bukan gerakan tangan. Koneksi persisten di thread terpisah karena event CDP
        hanya datang pada soket yang tetap terbuka.
        """
        import threading
        from websockets.sync.client import connect

        def run():
            try:
                with connect(self.cdp_ws, max_size=100 * 1024 * 1024) as sock:
                    # Iframe PX adalah OOPIF (cross-origin, proses terpisah), jadi
                    # request-nya TIDAK muncul di sesi target teratas. Tanpa auto-attach
                    # + Network.enable per sesi anak, log jaringan terlihat "bersih"
                    # padahal isi challenge tidak pernah terekam.
                    sock.send(json.dumps({
                        "id": 1, "method": "Target.setAutoAttach",
                        "params": {"autoAttach": True,
                                   "waitForDebuggerOnStart": False,
                                   "flatten": True}}))
                    sock.send(json.dumps({"id": 2, "method": "Network.enable",
                                          "params": {}}))
                    cid = 2
                    with open(path, "a") as f:
                        while True:
                            ev = json.loads(sock.recv())
                            m = ev.get("method") or ""
                            if m == "Target.attachedToTarget":
                                cid += 1
                                sid = (ev.get("params") or {}).get("sessionId")
                                if sid:
                                    sock.send(json.dumps({
                                        "id": cid, "method": "Network.enable",
                                        "params": {}, "sessionId": sid}))
                                continue
                            if not m.startswith("Network."):
                                continue
                            p = ev.get("params") or {}
                            rec = {"t": round(time.time() % 100000, 2), "m": m}
                            if m == "Network.requestWillBeSent":
                                rec["url"] = (p.get("request") or {}).get("url", "")[:4000]
                            elif m == "Network.responseReceived":
                                r = p.get("response") or {}
                                rec["url"] = r.get("url", "")[:4000]
                                rec["status"] = r.get("status")
                            elif m == "Network.loadingFailed":
                                rec.update({"error": p.get("errorText"),
                                            "type": p.get("type"),
                                            "blocked": p.get("blockedReason")})
                            else:
                                continue
                            f.write(json.dumps(rec) + "\n")
                            f.flush()
            except Exception:
                return

        threading.Thread(target=run, daemon=True).start()

    def cdp(self, method: str, params: dict = None):
        """Panggil CDP sekali (buka koneksi baru tiap panggilan — sederhana & aman)."""
        from websockets.sync.client import connect
        with connect(self.cdp_ws, max_size=80 * 1024 * 1024) as sock:
            sock.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
            while True:
                m = json.loads(sock.recv())
                if m.get("id") == 1:
                    return m

    def window_id(self) -> str | None:
        """Largest VISIBLE window that is not the 'Chromium clipboard' helper.

        ``--onlyvisible`` itu WAJIB, bukan kosmetik: tanpa filter itu daftar window
        ikut memuat window lama yang sudah tidak di-map, dan window seperti itu
        "menang" karena geometrinya lebih besar. Setiap ``import -window`` ke sana
        gagal dengan "Resource temporarily unavailable", sehingga SEMUA deteksi
        berbasis screenshot (posisi tombol PX dan ikon accessibility) mati total
        tanpa error yang terlihat — solver diam-diam jalan dengan koordinat tebak.

        Terukur: id 4194305 (unmapped) selalu terpilih dan selalu gagal, sementara
        id 2097155 (window nyata) ter-capture normal 23 KB.
        """
        best, area0 = None, 0
        # Beberapa varian pola, dari yang paling ketat.
        #
        # `--name ""` TIDAK cocok dengan apa pun saat digabung `--onlyvisible`
        # (terukur: mengembalikan kosong, solver lalu mati dengan
        # "browser window not found"), sedangkan `--name "."` cocok dan
        # mengembalikan window yang benar. Urutannya penting: jangan pernah
        # kembali ke daftar tanpa filter selama yang terlihat masih ada, karena
        # di situ window basi/unmapped ikut masuk dan `import` pasti gagal.
        cands: list[str] = []
        for pat in (".", ""):
            out = _run("xdotool", "search", "--onlyvisible", "--name", pat)
            cands = [w for w in out.splitlines() if w.strip()]
            if cands:
                break
        if not cands:
            cands = [w for w in _run("xdotool", "search", "--name", "").splitlines()
                     if w.strip()]
        ranked: list[tuple[int, str]] = []
        for w in dict.fromkeys(cands):
            title = _run("xdotool", "getwindowname", w)
            if not title or "clipboard" in title.lower():
                continue
            m = re.search(r"Geometry: (\d+)x(\d+)",
                          _run("xdotool", "getwindowgeometry", w))
            if not m:
                continue
            ranked.append((int(m.group(1)) * int(m.group(2)), w))
        ranked.sort(reverse=True)
        if not ranked:
            return None
        # Pilih yang benar-benar bisa di-capture.
        #
        # Di Xvfb ini Chromium praktis tidak pernah memetakan window utamanya
        # (terukur: yang ada hanya window 10x10 berjudul "chrome" dan
        # "Chromium clipboard", keduanya gagal di-`import`), jadi uji capture
        # sering tidak menemukan apa pun. Kalau begitu, JANGAN kembalikan None:
        # itu membuat solve mati total dengan "browser window not found",
        # padahal injeksi tombol lewat XTest tetap bekerja dan koordinat dipakai
        # absolut — solver masih bisa jalan memakai jalur koordinat layout.
        test = f"/tmp/_cap_{os.getpid()}.png"
        for _a, w in ranked:
            try:
                r = subprocess.run(["import", "-window", w, test],
                                   capture_output=True, timeout=25)
            except Exception:                                     # noqa: BLE001
                continue
            if r.returncode == 0 and os.path.exists(test) and os.path.getsize(test) > 5000:
                return w
        log.warning("window_id: tidak ada window yang bisa di-capture — memakai %s "
                    "apa adanya (deteksi gambar akan dilewati, jalur koordinat tetap jalan)",
                    ranked[0][1])
        return ranked[0][1]

    def title(self, wid: str = None) -> str:
        wid = wid or self.window_id()
        return _run("xdotool", "getwindowname", wid) if wid else ""

    def focus(self, wid: str) -> None:
        subprocess.run(["xdotool", "windowactivate", wid], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.6)

    def stop(self, timeout: float = 12.0) -> None:
        """Clean shutdown — SIGTERM so Chromium writes its cookie store."""
        if not self.pid:
            return
        subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={self.profile}"],
                       check=False)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not _run("pgrep", "-f", f"user-data-dir={self.profile}"):
                break
            time.sleep(0.5)
        else:
            subprocess.run(["pkill", "-9", "-f", f"user-data-dir={self.profile}"],
                           check=False)
            time.sleep(1)
        try:
            self.log.close()
        except Exception:
            pass

    def screenshot(self, path: str, wid: str = None) -> bool:
        wid = wid or self.window_id()
        if not wid:
            return False
        r = subprocess.run(["import", "-window", wid, path],
                           capture_output=True, text=True)
        return r.returncode == 0


def harvest_cookies(profile: str, port: int = 9334, timeout: float = 30.0) -> dict:
    """Read the profile's cookies by letting the browser decrypt them itself.

    Requires the profile's browser to be stopped first (see ``Browser.stop``).
    """
    proc = subprocess.Popen(
        [browser_binary(), f"--user-data-dir={profile}", "--no-sandbox",
         f"--remote-debugging-port={port}", "--remote-allow-origins=*",
         "--no-first-run", "--no-default-browser-check",
         "--window-size=900,600", "--window-position=0,0", "about:blank"],
        stdout=open("/tmp/px_harvest_cdp.log", "w"), stderr=subprocess.STDOUT,
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":99")})
    try:
        ver = None
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(1)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/json/version", timeout=3) as r:
                    ver = json.load(r)
                    break
            except Exception:
                continue
        if not ver:
            return {"error": "CDP endpoint never came up"}

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as r:
            targets = json.load(r)
        pages = [t for t in targets if t.get("type") == "page"]
        if not pages:
            return {"error": "no page target"}

        from websockets.sync.client import connect
        with connect(pages[0]["webSocketDebuggerUrl"], max_size=50 * 1024 * 1024) as sock:
            sock.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
            while True:
                msg = json.loads(sock.recv())
                if msg.get("id") == 1:
                    rows = (msg.get("result") or {}).get("cookies", [])
                    break

        cookies = {}
        for c in rows:
            if c["name"] in PX_COOKIE_NAMES or "hsprotect" in c.get("domain", ""):
                cookies[c["name"]] = c["value"]
        ua = ver.get("User-Agent", "") or ver.get("userAgent", "")
        return {"cookies": cookies, "total": len(rows),
                "browser": ver.get("Browser", ""), "user_agent": ua}
    finally:
        subprocess.run(["pkill", "-TERM", "-f", f"user-data-dir={profile}"], check=False)
        try:
            proc.wait(timeout=8)
        except Exception:
            subprocess.run(["pkill", "-9", "-f", f"user-data-dir={profile}"], check=False)


def cookie_header(cookies: dict) -> str:
    order = ["pxcts", "_pxvid", "_px3", "_pxde"]
    parts = [f"{n}={cookies[n]}" for n in order if n in cookies]
    parts += [f"{n}={v}" for n, v in cookies.items() if n not in order]
    return "; ".join(parts)
