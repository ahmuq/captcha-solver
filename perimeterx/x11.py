"""X11 driver for the PerimeterX press-and-hold gate.

Why this exists (measured on this deployment):
  * A browser launched with any ``--remote-debugging-*`` flag never renders the PX
    gate — PerimeterX detects the automation protocol's mere presence in the build.
    Same binary, same IP, without the flag and driven over X11: the gate renders and
    ``_px3`` is minted.
  * ``xdotool`` costs ~238 ms per call (~7 Hz) because every call spawns a process,
    while the PX sensor samples pointer motion at 60-125 Hz — a 7 Hz trail is itself
    a bot tell. ``python-xlib``'s XTest reaches ~2500 Hz here, enough for a real
    100 Hz trajectory.

So: launch the CloakBrowser binary directly (never through the Playwright wrapper),
drive it through XTest, and read cookies from the profile store.

Mouse control is GLOBAL to the X display, so callers must serialize this path
(``sessionless.py`` holds an asyncio lock).
"""
from __future__ import annotations

import math
import os
import random
import re
import subprocess
import time

from Xlib import X, display
from Xlib.ext import xtest

SAMPLE_HZ = 100
DT = 1.0 / SAMPLE_HZ


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout.strip()


def browser_binary() -> str:
    """Path to the CloakBrowser binary (env override, else newest *-pro build)."""
    env = os.environ.get("CLOAKBROWSER_BINARY_PATH", "").strip()
    if env and os.path.exists(env):
        return env
    root = os.path.expanduser("~/.cloakbrowser")
    cands = []
    if os.path.isdir(root):
        for name in os.listdir(root):
            p = os.path.join(root, name, "chrome")
            if os.path.exists(p) and "pro" in name:
                cands.append(p)
    if not cands:
        raise RuntimeError("no CloakBrowser binary found; set CLOAKBROWSER_BINARY_PATH")
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


class Hand:
    """Synthetic hand with physiological tremor, driven over XTest at 100 Hz."""

    def __init__(self, display_name: str = None):
        self.d = display.Display(display_name or os.environ.get("DISPLAY", ":99"))
        self.x, self.y = 640.0, 400.0
        # Amplitudo tremor harus menghasilkan perpindahan PIXEL nyata. Terukur: amplitudo
        # 0.25-0.9 px (dan dikali 0.55 di press_and_hold) jatuh di bawah 1 px, sehingga
        # 65% event dibuang oleh pembulatan integer — browser hanya melihat 32 Hz dari
        # loop yang mengklaim 92 Hz, dan pointer terbaca seperti hampir diam.
        self._tf = [random.uniform(7.5, 12.0) for _ in range(3)]
        self._ta = [random.uniform(1.1, 2.6) for _ in range(3)]
        self._tp = [random.uniform(0, math.tau) for _ in range(3)]
        self._drift = [random.uniform(-0.25, 0.25) for _ in range(2)]
        self._lx = self._ly = None
        self.emitted = 0            # event XTest yang benar-benar terkirim
        self.move_instant(self.x, self.y)

    # ---------- primitives ----------
    def _emit(self, x: float, y: float) -> bool:
        xi, yi = int(round(x)), int(round(y))
        if xi == self._lx and yi == self._ly:
            return False            # browsers ignore mousemove without movement
        xtest.fake_input(self.d, X.MotionNotify, x=xi, y=yi)
        self._lx, self._ly = xi, yi
        self.x, self.y = xi, yi
        self.emitted += 1
        return True

    def move_instant(self, x: float, y: float) -> None:
        self._lx = self._ly = None
        self._emit(x, y)
        self.d.sync()

    def _tremor(self, t: float):
        tx = sum(a * math.sin(math.tau * f * t + p)
                 for f, a, p in zip(self._tf, self._ta, self._tp))
        ty = sum(a * math.sin(math.tau * f * 0.85 * t + p + 1.1)
                 for f, a, p in zip(self._tf, self._ta, self._tp))
        return tx, ty

    def _drift_step(self):
        for i in range(2):
            self._drift[i] += random.uniform(-0.02, 0.02)
            self._drift[i] = max(-0.9, min(0.9, self._drift[i]))
        return self._drift[0], self._drift[1]

    # ---------- motion ----------
    def idle(self, seconds: float, cx: float = None, cy: float = None) -> None:
        """Rest the hand on the mouse: tremor + slow drift, no displacement."""
        cx = self.x if cx is None else cx
        cy = self.y if cy is None else cy
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            t = time.perf_counter() - t0
            tx, ty = self._tremor(t)
            dx, dy = self._drift_step()
            self._emit(cx + tx + dx, cy + ty + dy)
            self.d.sync()
            time.sleep(DT)

    def move_to(self, tx: float, ty: float, duration: float = None,
                submoves: int = None) -> None:
        """Minimum-jerk displacement, usually split into 1-3 submovements."""
        sx, sy = self.x, self.y
        dist = math.hypot(tx - sx, ty - sy)
        if duration is None:
            duration = min(0.95, max(0.22, 0.12 + dist / 2200 + random.uniform(0, 0.12)))
        if submoves is None:
            submoves = 1 if dist < 120 else random.choice([2, 2, 3])
        t0 = time.perf_counter()
        for k in range(submoves):
            frac = (k + 1) / submoves
            jx = 0.0 if frac == 1 else random.uniform(-8, 8)
            jy = 0.0 if frac == 1 else random.uniform(-8, 8)
            gx = sx + (tx - sx) * frac + jx
            gy = sy + (ty - sy) * frac + jy
            ax, ay = self.x, self.y
            st = time.perf_counter()
            while True:
                u = (time.perf_counter() - st) / (duration / submoves)
                if u >= 1.0:
                    break
                e = 10 * u**3 - 15 * u**4 + 6 * u**5
                trx, try_ = self._tremor(time.perf_counter() - t0)
                self._emit(ax + (gx - ax) * e + trx, ay + (gy - ay) * e + try_)
                self.d.sync()
                time.sleep(DT)
            if frac != 1 and random.random() < 0.6:
                self.idle(random.uniform(0.04, 0.12), self.x, self.y)
        self.move_instant(tx, ty)
        self.idle(random.uniform(0.05, 0.18), tx, ty)

    # ---------- buttons ----------
    def press(self) -> None:
        xtest.fake_input(self.d, X.ButtonPress, 1)
        self.d.sync()

    def release(self) -> None:
        xtest.fake_input(self.d, X.ButtonRelease, 1)
        self.d.sync()

    def click(self, x: float = None, y: float = None,
              hold_ms=(55, 120)) -> None:
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(random.uniform(0.06, 0.16))
        self.press()
        time.sleep(random.uniform(*hold_ms) / 1000.0)
        self.release()
        self.idle(random.uniform(0.1, 0.25))

    def _hold_tremor(self, seconds: float) -> None:
        """Mikro-tremor fisiologis selama tombol ditahan.

        Frekuensi ~9 Hz (rentang tremor tangan manusia 8-12 Hz), amplitudo 1-2 px supaya
        benar-benar menggeser piksel setelah pembulatan integer, plus drift lambat < 0.3 px
        agar tidak terlihat seperti osilasi sinus murni.

        BUKAN pola 100 Hz yang sudah terukur ditolak PX (0 dari 6): 100 Hz terlalu cepat
        untuk tangan manusia, sehingga terbaca sebagai sinyal sintetis. Yang ditiru di sini
        justru ketidakmampuan manusia menahan pointer benar-benar diam.
        """
        t0 = time.perf_counter()
        cx, cy = self.x, self.y
        while True:
            el = time.perf_counter() - t0
            if el >= seconds:
                break
            # 9 Hz utama + harmonik kecil, amplitudo 1.2 px -> bergeser 1-2 px nyata.
            tx = 1.2 * math.sin(2 * math.pi * 9.0 * el)
            ty = 0.9 * math.sin(2 * math.pi * 9.0 * el + 1.1)
            dx = 0.3 * math.sin(2 * math.pi * 0.35 * el)
            dy = 0.2 * math.sin(2 * math.pi * 0.28 * el + 0.7)
            self._emit(cx + tx + dx, cy + ty + dy)
            if int(el / DT) % 4 == 0:
                self.d.sync()
            time.sleep(DT)
        self._emit(cx, cy)
        self.d.sync()

    def press_and_hold(self, seconds: float = 9.0, x: float = None, y: float = None,
                       log=None, on_hold=None) -> float:
        """Hover masuk ke tombol -> tekan -> tahan TANPA gerakan -> lepas.

        Terukur A/B pada challenge PX asli (masing-masing satu session_id yang belum
        terpakai, karena challenge PX sekali pakai):

            pola tremor 100 Hz, 9 s  -> 0 dari 3 berhasil
            pola tremor 100 Hz, 5 s  -> 0 dari 3 berhasil
            pola DIAM, 4 s           -> 2 dari 5 berhasil ({"type":"succeeded"})

        Jadi PX menilai STABILITAS saat ditahan: pointer yang terus bergetar 100 Hz
        terbaca sintetis, sedangkan pointer yang benar-benar diam saat ditekan lolos.
        Jangan kembalikan tremor selama hold tanpa mengukur ulang A/B seperti di atas.

        Gerakan hanya terjadi SEBELUM menekan (hover + mendarat di tombol), karena
        pointer yang muncul begitu saja di atas tombol tidak pernah menghasilkan vonis.

        ``on_hold`` dipanggil sekali di tengah penahanan (mis. untuk screenshot) supaya
        pemanggil bisa memverifikasi bahwa press-nya benar-benar terdaftar.
        """
        if x is not None and y is not None:
            self.move_instant(x - random.uniform(110, 150), y - random.uniform(50, 70))
            time.sleep(random.uniform(0.2, 0.35))
            self.move_to(x, y, duration=random.uniform(0.35, 0.55))
        # DIAM sebelum menekan — JANGAN pakai idle().
        #
        # `idle()` memancarkan tremor ~100 Hz (satu _emit + d.sync per DT) dan itu
        # membocorkan gerakan sintetis ke PX tepat sebelum hold dimulai. Terukur: jalur
        # uji yang menghasilkan {"type":"succeeded"} memakai time.sleep() murni (nol event
        # motion) sebelum press, sedangkan produksi memakai idle() dan PX menolak/diam.
        # Jeda hening juga meniru perilaku manusia: tangan berhenti sejenak sebelum menekan.
        time.sleep(random.uniform(0.4, 0.6))
        self.press()
        t0 = time.perf_counter()
        if on_hold:
            time.sleep(min(1.5, seconds / 2))
            try:
                on_hold()
            except Exception:
                pass
            time.sleep(max(0.0, seconds - min(1.5, seconds / 2)))
        else:
            # DIAM TOTAL selama ditahan.
            #
            # Terukur A/B pada tombol asli: mikro-tremor fisiologis (~9 Hz, 1-2 px) LEBIH
            # BURUK — 0 diterima / 4 ditolak / 6 tanpa vonis, dibanding diam total yang
            # menghasilkan 3 akun. Gejala "tanpa vonis" muncul lagi karena pergeseran
            # pointer membuat progres tombol tidak selesai (PX menuntut pointer tetap di
            # dalam area tombol selama pengisian). Jadi untuk tombol ini, diam adalah
            # perilaku yang benar; jangan tambahkan gerakan saat ditahan.
            time.sleep(seconds)
        self.d.sync()
        held = time.perf_counter() - t0
        if log:
            log(f"press-hold {held:.1f}s DIAM (tanpa tremor), 0 event motion saat tahan")
        self.release()
        time.sleep(random.uniform(0.05, 0.12))
        return held
