"""Tangan manusia sintetis di atas X11/XTest untuk melewati penilaian biomekanik PX.

Kenapa modul ini ada:
  * `xdotool` menghasilkan ~7 Hz (tiap panggilan spawn proses, ~238 ms) — sensor PX
    menerima `mousemove` pada 60-125 Hz, jadi jejak 7 Hz terbaca sebagai bot.
  * XTest via python-xlib mencapai ~2500 Hz, cukup untuk menyusun trajectory nyata.
  * Sensor PX juga merekam seluruh sesi (bukan hanya saat hold), jadi tangan harus
    "hidup" terus: tremor fisiologis + drift lambat + koreksi mikro.

Model gerak:
  * perpindahan  : minimum-jerk (10t^3-15t^4+6t^5), sering 2 sub-gerakan
                   (ballistic + corrective) seperti tangan asli.
  * tremor       : 3 sinusoid 8-12 Hz, amplitudo 0.3-1.2 px (tremor fisiologis).
  * drift        : random walk frekuensi rendah (0.2-0.6 Hz).
  * sampling     : 100 Hz (10 ms) — setara polling mouse nyata.
"""
from __future__ import annotations

import math
import random
import time

from Xlib import X, display
from Xlib.ext import xtest

SAMPLE_HZ = 100
DT = 1.0 / SAMPLE_HZ


class Hand:
    """Kursor dengan dinamika biomekanik; semua gerak disampling 100 Hz."""

    def __init__(self, display_name: str = ":99"):
        self.d = display.Display(display_name)
        self.x = 640.0
        self.y = 400.0
        # fase tremor acak per sesi (manusia punya frekuensi tremor khas)
        self._tf = [random.uniform(7.5, 12.0) for _ in range(3)]
        self._ta = [random.uniform(0.25, 0.9) for _ in range(3)]
        self._tp = [random.uniform(0, math.tau) for _ in range(3)]
        self._drift = [random.uniform(-0.25, 0.25) for _ in range(2)]
        self.move_instant(self.x, self.y)

    # ---------- primitif ----------
    def _emit(self, x: float, y: float) -> None:
        xi, yi = int(round(x)), int(round(y))
        if xi == getattr(self, "_lx", None) and yi == getattr(self, "_ly", None):
            return                      # browser mengabaikan mousemove tanpa perubahan
        xtest.fake_input(self.d, X.MotionNotify, x=xi, y=yi)
        self._lx, self._ly = xi, yi
        self.x, self.y = xi, yi

    def move_instant(self, x: float, y: float) -> None:
        self._lx = self._ly = None
        self._emit(x, y)
        self.d.sync()

    def _tremor(self, t: float) -> tuple[float, float]:
        tx = sum(a * math.sin(math.tau * f * t + p)
                 for f, a, p in zip(self._tf, self._ta, self._tp))
        ty = sum(a * math.sin(math.tau * f * 0.85 * t + p + 1.1)
                 for f, a, p in zip(self._tf, self._ta, self._tp))
        return tx, ty

    def _drift_step(self) -> tuple[float, float]:
        for i in range(2):
            self._drift[i] += random.uniform(-0.02, 0.02)
            self._drift[i] = max(-0.9, min(0.9, self._drift[i]))
        return self._drift[0], self._drift[1]

    # ---------- gerak ----------
    def idle(self, seconds: float, cx: float | None = None,
             cy: float | None = None) -> None:
        """Tangan beristirahat di atas mouse: tremor + drift, tanpa perpindahan."""
        cx = self.x if cx is None else cx
        cy = self.y if cy is None else cy
        t0 = time.perf_counter()
        n = 0
        while time.perf_counter() - t0 < seconds:
            t = time.perf_counter() - t0
            tx, ty = self._tremor(t)
            dx, dy = self._drift_step()
            self._emit(cx + tx + dx, cy + ty + dy)
            n += 1
            self.d.sync()
            time.sleep(DT)
        return None

    def move_to(self, tx: float, ty: float, duration: float | None = None,
                submoves: int | None = None) -> None:
        """Perpindahan minimum-jerk, sering dipecah jadi 1-3 sub-gerakan."""
        sx, sy = self.x, self.y
        dist = math.hypot(tx - sx, ty - sy)
        if duration is None:
            # Fitts-ish: makin jauh makin lama, ~0.25-0.9 s
            duration = min(0.95, max(0.22, 0.12 + dist / 2200 + random.uniform(0, 0.12)))
        if submoves is None:
            submoves = 1 if dist < 120 else random.choice([2, 2, 3])
        t0 = time.perf_counter()
        for k in range(submoves):
            frac = (k + 1) / submoves
            # sub-gerakan terakhir menuju target, yang sebelumnya undershoot
            jx = 0.0 if frac == 1 else random.uniform(-8, 8)
            jy = 0.0 if frac == 1 else random.uniform(-8, 8)
            gx = sx + (tx - sx) * frac + jx
            gy = sy + (ty - sy) * frac + jy
            ax, ay = self.x, self.y
            dur = duration / submoves
            st = time.perf_counter()
            while True:
                u = (time.perf_counter() - st) / dur
                if u >= 1.0:
                    break
                e = 10 * u**3 - 15 * u**4 + 6 * u**5     # minimum-jerk
                trx, try_ = self._tremor(time.perf_counter() - t0)
                self._emit(ax + (gx - ax) * e + trx, ay + (gy - ay) * e + try_)
                self.d.sync()
                time.sleep(DT)
            # koreksi kecil setelah sub-gerakan (manusia selalu menyesuaikan)
            if frac != 1 and random.random() < 0.6:
                self.idle(random.uniform(0.04, 0.12), self.x, self.y)
        # mendarat tepat di target
        self.move_instant(tx, ty)
        self.idle(random.uniform(0.05, 0.18), tx, ty)

    # ---------- tombol ----------
    def press(self) -> None:
        xtest.fake_input(self.d, X.ButtonPress, 1)
        self.d.sync()

    def release(self) -> None:
        xtest.fake_input(self.d, X.ButtonRelease, 1)
        self.d.sync()

    def click(self, x: float | None = None, y: float | None = None,
              hold_ms: tuple[int, int] = (55, 120)) -> None:
        if x is not None and y is not None:
            self.move_to(x, y)
        time.sleep(random.uniform(0.06, 0.16))
        self.press()
        time.sleep(random.uniform(*hold_ms) / 1000.0)
        self.release()
        self.idle(random.uniform(0.1, 0.25))

    def press_and_hold(self, seconds: float = 8.0, x: float | None = None,
                       y: float | None = None, log=None) -> float:
        """Tekan, tahan dengan tremor+drift nyata pada 100 Hz, lalu lepas.

        Meniru pola manusia: pendekatan -> jeda -> downstroke cepat -> tahan stabil
        dengan tremor -> lepas. Mengembalikan durasi tahan sebenarnya.
        """
        if x is not None and y is not None:
            self.move_to(x, y)
        self.idle(random.uniform(0.35, 0.9))          # jeda sebelum menekan

        # downstroke: sedikit di atas target lalu turun ke pusat (tekanan jari)
        self.move_to(x - random.uniform(1, 3), y - random.uniform(2, 5), duration=0.12)
        time.sleep(random.uniform(0.02, 0.06))
        self.press()
        t0 = time.perf_counter()
        n = 0
        while True:
            el = time.perf_counter() - t0
            if el >= seconds:
                break
            tx, ty = self._tremor(el)
            dx, dy = self._drift_step()
            # gerak jari yang menekan: amplitudo lebih kecil dari saat idle
            self._emit(x + (tx + dx) * 0.55, y + (ty + dy) * 0.55)
            n += 1
            self.d.sync()
            time.sleep(DT)
        held = time.perf_counter() - t0
        if log:
            log(f"    hold {held:.1f}s, {n} event ({n/held:.0f} Hz)")
        self.release()
        # lepas: tangan bergerak menjauh perlahan
        time.sleep(random.uniform(0.05, 0.12))
        return held
