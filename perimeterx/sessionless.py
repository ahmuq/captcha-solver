"""PerimeterX SESSIONLESS solver — solves the CALLER's challenge, not our own.

Contract parity with a cloud solver's ``PXCaptchaSessionlessPressAndHold`` task: the
caller supplies its challenge identity (``challenge_url`` / ``uuid`` / ``vid``) and gets
back the ``_px3`` minted for THAT session.

Why a local wrapper page (the key discovery)
--------------------------------------------
The challenge page (``iframe.hsprotect.net``) does NOT render on its own. Reading its
inline script over CDP shows the flow:

    window.addEventListener("message", ...)      // messages from the PARENT frame
      case "block":       d(e.jsonResponse, e.requestUrl); break
      case "setToWindow": p(e.key, e.value); break
    function d(t, n) { window._pxUuid = t.uuid; window._pxVid = t.vid; i("captcha") }
    captcha: `${appId}/captcha.js?a=c&m=0&u=${window._pxUuid}&v=${window._pxVid}`

So ``captcha.js`` — the script that renders the press-and-hold button — is loaded only
after the parent frame posts ``{type:"block", jsonResponse:{uuid, vid}}``. Measured on a
bare top-level load: ``_pxAppId`` set, ``#px-captcha`` present but EMPTY, ``_pxVid``
undefined, page blank. Microsoft's signup page is that parent; opening the iframe
standalone can never work.

This module therefore serves a minimal local wrapper that plays the parent's role: it
embeds the caller's challenge URL and posts the caller's ``uuid``/``vid`` into it. With
that, the gate renders (verified: "Press and hold" button visible, challenge emits
``_px3`` / ``_pxvid`` / ``_pxde``).

The wrapper also collects what the challenge posts back to its parent:

    window.parent.postMessage({type:"cookie", name, value, expires}, "*")

which is how ``_px3`` is harvested here — no cookie-store decryption and no CDP relaunch
on the solve path.

Two hard constraints carry over from the harvest path:

* the browser must run **without** ``--remote-debugging-*`` (that flag alone stops the
  gate from rendering), so the wrapper is driven over X11/XTest;
* pointer control is global to the X display, so this path is serialized.
"""
from __future__ import annotations

import asyncio
import base64
import http.server
import json
import logging
import os
import random
import re
import shutil
import socketserver
import threading
import time

from common.concurrency import solve_slot

from .browser import Browser
from .seed import seed_visitor
from .x11 import Hand

log = logging.getLogger(__name__)

IFRAME_BASE = "https://iframe.hsprotect.net/index.html"
DEFAULT_APP_ID = "PXzC5j78di"
WRAPPER_HTML = os.path.join(os.path.dirname(__file__), "px_host.html")

# Pointer control is global to the X display: two concurrent X11 solves would fight over
# one cursor, so this path is serialized regardless of SOLVER_MAX_CONCURRENT.
_x11_lock = asyncio.Lock()


def build_iframe_url(app_id: str = None, session_id: str = None) -> str:
    from urllib.parse import urlencode
    q = {}
    if app_id:
        q["app_id"] = app_id
    if session_id:
        q["session_id"] = session_id
    return f"{IFRAME_BASE}?{urlencode(q)}" if q else IFRAME_BASE


class _Wrapper:
    """Serve the parent-frame wrapper and collect what the challenge reports."""

    def __init__(self, challenge_url: str, uuid: str, vid: str, port: int = 0):
        tpl = open(WRAPPER_HTML).read()
        self.page = (tpl.replace("__CHALLENGE__", challenge_url)
                        .replace("__UUID__", json.dumps(uuid or ""))
                        .replace("__VID__", json.dumps(vid or "")))
        self.events = []
        self.cookies = {}
        self.ua = ""
        self.rendered = threading.Event()
        # Terminal event: PX sudah selesai menilai hold (bukan sekadar tombol muncul).
        self.solved = threading.Event()
        # Riwayat _px3: PX memutarnya beberapa kali per sesi; yang terakhir = final.
        self.px3_history = []
        # PX menolak hold: terukur, event "failed" datang walau `_px3` tetap terbit —
        # token itu tidak sah, dan itulah sebabnya caller ditolak
        # (state=riskChallengeRequired + challenge baru diterbitkan).
        self.failed = threading.Event()
        self.failure_type = None
        self._lock = threading.Lock()
        wrapper = self

        class H(http.server.BaseHTTPRequestHandler):
            def _send(self, body, ctype="text/html; charset=utf-8"):
                b = body.encode() if isinstance(body, str) else body
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                self._send(wrapper.page)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n).decode("utf-8", "replace")
                wrapper.record(raw)
                self._send("ok", "text/plain")

            def log_message(self, *a):
                pass

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), H)
        self.srv.daemon_threads = True
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def record(self, raw: str) -> None:
        try:
            ev = json.loads(raw)
        except Exception:
            return
        with self._lock:
            self.events.append(ev)
            # Simpan payload event apa adanya ke disk: PX menyertakan ALASAN penolakan
            # di dalam event "failed", dan tebakan (frekuensi, durasi, visitor) sudah
            # tiga kali meleset — lebih baik baca alasan yang PX sebutkan sendiri.
            try:
                with open("/tmp/px_events.jsonl", "a") as f:
                    f.write(json.dumps(ev, default=str)[:4000] + "\n")
            except Exception:
                pass
            data = ev.get("data")
            if isinstance(data, dict):
                t = data.get("type")
                if t == "rendered":
                    self.rendered.set()
                # PX mengirim event bertipe ke parent. Terukur pada sesi yang BERHASIL:
                # {"type":"succeeded"} — bukan "solved"/"success". Sebelumnya event ini
                # tidak dikenali sehingga hold yang SUKSES tetap dilaporkan gagal.
                if t in ("succeeded", "solved", "success", "block", "challengeSolved"):
                    self.solved.set()
                if t in ("failed", "error", "expired"):
                    self.failed.set()
                    self.failure_type = t
                if t == "cookie" and data.get("name"):
                    self.cookies[data["name"]] = data.get("value") or ""
                    if data["name"] == "_px3" and data.get("value"):
                        # PX memutar _px3 beberapa kali selama satu sesi; simpan riwayat
                        # supaya pemanggil bisa memakai token terakhir (yang final).
                        self.px3_history.append(data["value"])
            # UA dilaporkan terpisah (kind='ua'): _px3 terikat ke UA, jadi caller harus
            # me-replay dengan UA yang sama persis.
            if ev.get("kind") == "ua" and ev.get("value"):
                self.ua = ev["value"]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def close(self) -> None:
        for fn in (self.srv.shutdown, self.srv.server_close):
            try:
                fn()
            except Exception:
                pass


def _find_a11y_icon(br: Browser, wid: str, height: int = 900):
    """Lokasi ikon bulat "Accessible challenge" di kiri tombol press-and-hold.

    Ini BUKAN hiasan: pada challenge PX, ikon accessibility membuka jalur alternatif yang
    tidak dinilai biomekanik. Terukur dari repo LainsNL/OutlookRegister — alurnya klik
    ``[aria-label="可访问性挑战"]`` (Accessible challenge) lalu klik
    ``[aria-label="再次按下"]`` (Press again), tanpa menahan tombol sama sekali.

    Deteksi visual (tanpa CDP, karena CDP merusak render): pada baris band tombol, cari
    segmen gelap paling KIRI yang lebarnya 25-60 px dan terpisah celah dari badan pill.
    Terukur pada render nyata: ikon di x 486-525, y 152-183 -> pusat ~(505, 167).
    """
    shot = f"/tmp/_a11y_{os.getpid()}.png"
    if not br.screenshot(shot, wid):
        return None
    gray = f"/tmp/_a11yg_{os.getpid()}.png"
    try:
        import subprocess

        def _c(*a):
            return subprocess.run(["convert", *a], capture_output=True, text=True)

        _c(shot, "-colorspace", "Gray", "-depth", "8", gray)
        txt = _c(gray, "-depth", "8", "txt:-").stdout

        rows = {}
        pat = re.compile(r"^(\d+),(\d+):\s*\(([\d.]+)")
        for line in txt.splitlines():
            m = pat.match(line)
            if not m:
                continue
            rows.setdefault(int(m.group(2)), []).append(
                (int(m.group(1)), float(m.group(3)) / 255.0))

        pts = []
        for y in sorted(rows):
            if not (30 <= y <= height - 30):
                continue
            segs = _segments_of(rows[y])
            if len(segs) < 2:
                continue
            left = min(segs, key=lambda s: s[0])
            w = left[1] - left[0]
            if not (25 <= w <= 60):
                continue
            # Ikon harus berada di KIRI tombol, bukan sembarang segmen kecil di halaman.
            # Jangan mensyaratkan badan pill ada di baris yang SAMA: terukur pada render
            # nyata ikon (x 486-525) dan pill (x 535-792) bisa berada di baris berbeda,
            # dan syarat "satu baris" membuat ikon tidak pernah terdeteksi sehingga jalur
            # accessibility tidak pernah dicoba.
            rest = [s for s in segs if s is not left]
            if rest and min(s[0] for s in rest) > left[1] + 5:
                pts.append(((left[0] + left[1]) // 2, y))
        if not pts:
            return None
        xs = sorted(p[0] for p in pts)
        ys = sorted(p[1] for p in pts)
        return xs[len(xs) // 2], ys[len(ys) // 2]
    except Exception as e:                                       # noqa: BLE001
        log.debug("a11y icon locate failed: %s", e)
        return None
    finally:
        for p in (shot, gray):
            try:
                os.remove(p)
            except Exception:
                pass


def _wait_a11y_gone(br, wid, height: int = 900, timeout: float = 14.0) -> bool:
    """Tunggu ikon "Accessible challenge" HILANG dari layar.

    Ini penanda lolos yang dipakai repo LainsNL/OutlookRegister: setelah klik ikon dan
    "Press again", PX memutar spinner; kalau challenge selesai, ikon accessibility hilang
    (halaman pindah ke langkah berikutnya). Kalau masih ada, challenge belum selesai dan
    harus diklik ulang — bukan dianggap gagal.

    Kembalikan True kalau ikon hilang sebelum timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _find_a11y_icon(br, wid, height) is None:
            return True
        time.sleep(0.8)
    return False


def _segments_of(px, gap: int = 6):
    """Segmen piksel gelap pada satu baris dari data piksel di memori."""
    xs = sorted(x for x, v in px if v < 0.72)
    if not xs:
        return []
    segs, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > gap:
            segs.append((start, prev))
            start = x
        prev = x
    segs.append((start, prev))
    return segs


def _find_gate_button(br: Browser, wid: str, height: int = 900):
    """Locate the press-and-hold button from a window screenshot.

    The button is a rounded-rectangle OUTLINE (dark, ~1 px) around a white interior, with
    an icon and a "PRESS & HOLD" label inside. Colour masking fails because the card
    background is white too, so we look for the outline-pair signature on a row: two dark
    pixels 200-620 px apart with a mostly-white interior between them. Several rows
    qualify (top edge, text row, bottom edge); we group them into bands and use the centre
    of the widest band, which lands on the button body.
    """
    shot = f"/tmp/_gate_{os.getpid()}.png"
    if not br.screenshot(shot, wid):
        # Terlihat di produksi: deteksi "gagal" tanpa jejak apa pun karena jalur ini
        # mengembalikan None sebelum logging apa pun. Akibatnya solver diam-diam jatuh ke
        # fallback koordinat, dan kita tidak pernah tahu screenshot-nya yang gagal.
        log.warning("gate button: screenshot gagal (wid=%s) — deteksi dilewati", wid)
        return None
    gray = f"/tmp/_gg_{os.getpid()}.png"
    try:
        import subprocess

        def _c(*a):
            return subprocess.run(["convert", *a], capture_output=True, text=True)

        _c(shot, "-colorspace", "Gray", "-depth", "8", gray)
        txt = _c(gray, "-depth", "8", "txt:-").stdout

        rows = {}
        pat = re.compile(r"^(\d+),(\d+):\s*\(([\d.]+)")
        for line in txt.splitlines():
            m = pat.match(line)
            if not m:
                continue
            rows.setdefault(int(m.group(2)), []).append(
                (int(m.group(1)), float(m.group(3)) / 255.0))

        hits = []
        for y in sorted(rows):
            if not (30 <= y <= height - 30):
                continue
            px = rows[y]
            dark = [x for x, v in px if v < 0.72]
            if len(dark) < 2:
                continue
            x0, x1 = min(dark), max(dark)
            width = x1 - x0
            if not (200 <= width <= 620):
                continue
            inner = [v for x, v in px if x0 + 8 < x < x1 - 8]
            if not inner:
                continue
            mean = sum(inner) / len(inner)
            # Dua gaya tombol yang sah, keduanya harus dikenali:
            #   OUTLINE — interior putih (mean > 0.90)
            #   FILLED  — badan abu-abu terisi dengan teks putih "PRESS & HOLD"
            #             (terukur pada render yang benar: interior abu-abu, mean ~0.5-0.8).
            # Detektor lama hanya menerima OUTLINE, sehingga tombol FILLED yang sudah
            # render sempurna ditolak dan hold tidak pernah mendarat di tombol.
            if mean > 0.90 or 0.35 <= mean <= 0.85:
                hits.append((y, x0, x1))
        if not hits:
            # Simpan render yang GAGAL terdeteksi. Tanpa ini, kegagalan deteksi di
            # produksi tidak bisa didiagnosis: kita hanya tahu "return None" tanpa tahu
            # apa yang sebenarnya tampil. Ini yang membuat solver bergantung pada
            # fallback koordinat hardcoded yang kebetulan pas.
            try:
                shutil.copy(shot, f"/tmp/px_gatefail_{os.getpid()}_{int(time.time())}.png")
            except Exception:
                pass
            return None

        bands, cur = [], [hits[0]]
        for h in hits[1:]:
            if h[0] - cur[-1][0] <= 2:
                cur.append(h)
            else:
                bands.append(cur)
                cur = [h]
        bands.append(cur)

        # Pilih band yang paling mungkin BADAN TOMBOL, bukan ikon di kiri tombol.
        #
        # Terukur pada render nyata: ikon bulat (x 483-525) dan pill (x 532-784) berada di
        # baris yang sama. Band gabungan membuat titik tengah meleset ~19 px ke kiri dan
        # hold mendarat di celah antara ikon dan pill, sehingga PX tidak menilai hold-nya.
        def _score(b):
            w = max(x1 for _, _, x1 in b) - min(x0 for _, x0, _ in b)
            h = b[-1][0] - b[0][0] + 1
            # Tepi kanan dulu, baru luas.
            #
            # Pill adalah elemen paling KANAN pada challenge ini (~793), sedangkan baris
            # teks berhenti di ~676. Dengan skor luas saja, band teks bisa menang dan
            # pusatnya jatuh ke ~522 — terukur, hold di situ tidak menyentuh tombol.
            # Menjadikan tepi kanan kunci utama membuat band pill selalu menang.
            right = max(x1 for _, _, x1 in b)
            return (right, w * h)

        band = max(bands, key=_score)
        y_top, y_bot = band[0][0], band[-1][0]
        height = y_bot - y_top + 1
        y_mid = (y_top + y_bot) // 2

        def _segs_from_row(px, gap=6):
            """Segmen piksel gelap pada satu baris, dari data piksel yang SUDAH di memori.

            Jangan ambil screenshot per baris di sini: itu berarti ~86 screenshot +
            convert untuk satu deteksi tombol dan terukur memakan ~40 detik per percobaan
            (hold1=+46s padahal hold-nya sendiri cuma 4 s). Datanya sudah ada di `rows`.
            """
            xs = sorted(x for x, v in px if v < 0.72)
            if not xs:
                return []
            segs, start, prev = [], xs[0], xs[0]
            for x in xs[1:]:
                if x - prev > gap:
                    segs.append((start, prev))
                    start = x
                prev = x
            segs.append((start, prev))
            return segs

        # Titik tengah horizontal: pakai baris yang memuat TEPAT DUA segmen gelap.
        #
        # Terukur pada render nyata (peta piksel, bukan perkiraan): baris atas pill hanya
        # memuat tepi kiri (x 538-545) dan tepi kanan (x 782-789) -> center x=663. Ikon
        # bulat muncul beberapa baris di bawahnya sebagai segmen KETIGA (x 501-517), dan
        # menyertakannya menggeser center ke 639 sehingga hold mendarat di celah antara
        # ikon dan pill. Baris dua-segmen = badan pill saja.
        # Cari BADAN TOMBOL, bukan ikon di kiri.
        #
        # Terukur pada render nyata. Tombol punya dua gaya dan masing-masing menghasilkan
        # pola segmen berbeda pada satu baris:
        #
        #   OUTLINE (belum ditekan) : [(538,545), (782,789)]      -> dua TEPI, lebar ~8 px
        #   FILLED  (sudah ditekan) : [(488,523), (535,792)]      -> ikon + BADAN penuh
        #
        # Jadi "dua segmen" BUKAN penanda yang aman: pada gaya FILLED, dua segmen itu ikon
        # + badan, dan titik tengah gabungannya (640) meleset 23 px ke kiri dari pusat
        # tombol (663). Aturan yang menangani keduanya: ambil segmen TERLEBAR pada baris;
        # kalau lebarnya >= 150 px itu badan tombol (FILLED) dan pusatnya langsung dipakai.
        # Kalau tidak ada segmen selebar itu, baru pakai pasangan dua tepi (OUTLINE).
        rows_right = []                                    # (y, tepi kanan)
        for y, rx0, rx1 in band:
            segs = _segs_from_row(rows[y])
            if not segs:
                continue
            # Semua segmen ikut dihitung, TANPA ambang lebar.
            #
            # Ambang lebar (>=60 px) pernah dipakai di sini dan itu salah: pada gaya
            # OUTLINE tombol hanya tampil sebagai dua tepi tipis (~8 px), jadi ambang itu
            # membuang tepi kanan pill dan menyisakan baris TEKS sebagai satu-satunya
            # baris yang lolos -> tepi kanan terbaca 652 dan pusat jatuh ke 522.
            # Terukur pada band x=486..793 yang jelas memuat pill.
            rows_right.append((y, max(s[1] for s in segs)))
        confident = bool(rows_right)
        if confident:
            # Tepi kanan TERJAUH di SELURUH band = tepi kanan pill.
            #
            # Harus lintas-baris, bukan per baris. Baris teks tombol ("Press and Hold")
            # juga menghasilkan segmen lebar, tapi tepinya berhenti di ~645 sedangkan
            # pill mencapai ~792. Kalau pusat dihitung per baris lalu baris TERLEBAR
            # yang dipilih, baris TEKS yang menang (lebar 307 > pill 257) dan pusatnya
            # jatuh ke ~515-522 — terukur, dan hold di situ sama sekali tidak
            # menyentuh tombol. Mengambil tepi kanan terjauh membuat baris teks tidak
            # bisa menang, karena tepinya selalu lebih kiri daripada tepi pill.
            R = max(r for _, r in rows_right)
            ys = [y for y, r in rows_right if r >= R - 6]
            y_mid = ys[len(ys) // 2]
            cx = R - 130
        else:
            # JANGAN pakai titik tengah band gabungan sebagai fallback.
            #
            # Terukur berulang kali: titik tengah band memasukkan ikon bulat di kiri pill
            # sehingga menghasilkan x~640, dan hold di situ mendarat di celah ikon-pill —
            # PX tidak menilai hold-nya sama sekali (percobaan selalu ditolak). Nilai itu
            # juga sempat tersimpan sebagai `last_good_button` sehingga mencemari percobaan
            # berikutnya. Kalau tidak ada baris yang yakin, pakai koordinat baik terakhir
            # bila ada; kalau tidak ada sama sekali, laporkan gagal deteksi.
            prev = getattr(br, "last_good_button", None)
            log.info("baris segmen tidak yakin — pakai koordinat valid terakhir %s "
                     "(band y=%d..%d)", prev, y_top, y_bot)
            if prev is None:
                log.warning("tombol tidak terdeteksi dan belum ada koordinat valid — "
                            "menolak memakai titik tengah band (terukur meleset)")
                try:
                    shutil.copy(shot, f"/tmp/px_gatefail_{os.getpid()}_{int(time.time())}.png")
                except Exception:
                    pass
                return None
            cx, y_mid = prev[0], prev[1]
        band_x0 = min(x0 for _, x0, _ in band)
        band_x1 = max(x1 for _, _, x1 in band)
        # Deteksi kadang mengembalikan band 2-3 px (tepi atas tombol, bukan badannya) dan
        # hold yang mendarat di situ TIDAK terdaftar PX. Simpan hanya deteksi yang YAKIN
        # sebagai koordinat terakhir yang diketahui baik — nilai fallback tidak boleh
        # disimpan, karena itu mencemari percobaan berikutnya dengan x yang terukur gagal.
        if confident and height >= 14:
            br.last_good_button = (cx, y_mid)
        br.last_band_height = height
        log.info("gate button: band y=%d..%d x=%d..%d centre=(%d,%d) width=%d",
                 y_top, y_bot, band_x0, band_x1, cx, y_mid, band_x1 - band_x0)
        return cx, y_mid
    except Exception as e:                                       # noqa: BLE001
        # INFO, bukan DEBUG: kegagalan deteksi harus terlihat di log produksi. Saat
        # DEBUG, satu-satunya jejaknya hilang dan solver tampak "tidak menemukan tombol"
        # tanpa alasan apa pun — persis kondisi yang membuat kita bergantung pada
        # fallback koordinat hardcoded tanpa tahu kenapa.
        log.warning("button locate failed: %s", e)
        try:
            shutil.copy(shot, f"/tmp/px_gatefail_exc_{os.getpid()}_{int(time.time())}.png")
        except Exception:
            pass
        return None
    finally:
        for p in (shot, gray):
            try:
                os.remove(p)
            except Exception:
                pass


def _shot_diff(a: str, b: str) -> int:
    """Jumlah piksel berbeda antara dua PNG (0 = identik, -1 = gagal).

    ImageMagick menulis metrik ke STDERR, bukan stdout — membaca stdout selalu
    menghasilkan -1 dan menyamarkan perubahan nyata sebagai "tidak ada diff".
    """
    import subprocess
    try:
        r = subprocess.run(["compare", "-metric", "AE", a, b, "null:"],
                           capture_output=True, text=True)
        txt = (r.stderr or r.stdout or "").strip()
        return int(float(txt.split()[0]))
    except Exception:
        return -1


def _dark_segments(br, y: int, x0: int, x1: int, gap: int = 6) -> list:
    """Segmen piksel gelap pada satu baris, dipisah celah >= ``gap`` piksel.

    Dipakai untuk memisahkan tepi kiri/kanan pill dari ikon di sebelahnya. Ambang gelap
    (v < 0.72) sama dengan yang dipakai ``_find_gate_button`` supaya konsisten.
    """
    import re as _re
    import subprocess as _sp
    shot = f"/tmp/_row_{y}.png"
    try:
        br.screenshot(shot, getattr(br, "wid", None))
        r = _sp.run(["convert", shot, "-colorspace", "gray", "-crop",
                     f"{x1 - x0 + 1}x1+{x0}+{y}", "txt:-"],
                    capture_output=True, text=True)
        xs = []
        for line in r.stdout.splitlines():
            m = _re.match(r"(\d+),0: \((\d+)", line)
            if m:
                x, v = int(m.group(1)) + x0, int(m.group(2)) / 255.0
                if v < 0.72:
                    xs.append(x)
    except Exception:
        return []
    finally:
        try:
            os.remove(shot)
        except Exception:
            pass
    if not xs:
        return []
    xs.sort()
    segs, start, prev = [], xs[0], xs[0]
    for x in xs[1:]:
        if x - prev > gap:
            segs.append((start, prev))
            start = x
        prev = x
    segs.append((start, prev))
    return segs


def _egress_ip(proxy: str, timeout: float = 8.0) -> str:
    """IP keluar lewat proxy, atau "" kalau gagal.

    Dipakai untuk mendeteksi penyebab kegagalan yang paling sering terukur: koneksi
    seluler di HP drop dan IP berganti DI TENGAH solve. PX mengikat challenge ke IP, jadi
    saat IP berubah PX membuang sesi TANPA mengirim `failed` maupun `succeeded` — gejala
    "tanpa vonis". Tanpa pengukuran ini, kegagalan itu tampak seperti bug biomekanik.
    """
    import subprocess
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", str(int(timeout)), "-x", proxy,
             "https://api.ipify.org"],
            capture_output=True, text=True)
        ip = (r.stdout or "").strip()
        return ip if ip.count(".") == 3 else ""
    except Exception:
        return ""


def _band_height(br: Browser, wid: str) -> int:
    """Tinggi band tombol yang terakhir terdeteksi (0 bila tidak ada).

    Dipakai untuk menolak deteksi yang tidak yakin: band setinggi 2-3 px adalah tepi
    atas tombol, bukan badannya, dan hold yang mendarat di situ tidak terdaftar PX.
    """
    try:
        return int(getattr(br, "last_band_height", 0) or 0)
    except Exception:
        return 0


def _result(t0, cookies, ua, gate, actuated, error=None, note=None, events=0,
            accepted=False):
    """Bentuk respons solver.

    PENTING: ``solved`` harus mencerminkan apakah PX MENERIMA hold-nya (event
    ``{"type":"succeeded"}``), bukan sekadar apakah ``_px3`` terbit. Terukur: ``_px3``
    terbit bahkan saat hold ditolak, dan token itu selalu ditolak Microsoft di
    risk/verify #2 (state=riskChallengeRequired). Solver yang melaporkan solved=true
    untuk token mati membuat caller membuang satu percobaan penuh (rotasi IP + ~1 MB)
    untuk hasil yang pasti gagal.

    ``px3`` tetap dikembalikan apa adanya supaya caller bisa memeriksa sendiri.
    """
    px3 = (cookies or {}).get("_px3")
    out = {
        "solved": bool(actuated and px3 and accepted),
        "px3": px3 or "",
        "hold_accepted": bool(accepted),
        "cookies": cookies or {},
        "cookie_header": "; ".join(f"{k}={v}" for k, v in (cookies or {}).items()),
        "user_agent": ua or "",
        "gate_reached": bool(gate),
        "press_hold_actuated": bool(actuated),
        "px3_rotated": bool(px3),
        "mode": "sessionless",
        "elapsed": round(time.time() - t0, 1),
        "events": events,
        "replay_contract": {"bound_to": ["_pxvid", "client_ip", "user_agent"]},
    }
    if px3 and not accepted:
        out["note"] = ((note + "; ") if note else "") + \
            "PX tidak mengirim event succeeded — token kemungkinan interim"
    if note and "note" not in out:
        out["note"] = note
    if error:
        out["error"] = error
    return out


async def _do_hold(br, hand, wid, bx, by, hold_s, attempt, t0, _ph, log):
    """Jalankan satu press-and-hold penuh (jalur cadangan bila a11y tidak tersedia).

    Dipisah jadi fungsi supaya pemanggilnya bisa memilih jalur (a11y vs hold) tanpa
    menambah kedalaman indentasi — percobaan pertama menggabungkannya langsung dan
    menghasilkan IndentationError.

    Diagnostik "press terdaftar?" bersifat OPT-IN (PX_HOLD_DIAG=1): terukur jalur uji yang
    menghasilkan `succeeded` TIDAK mengambil screenshot selama hold, dan operasi X di
    tengah penahanan berisiko mengganggu press yang sedang aktif.
    """
    diag = os.environ.get("PX_HOLD_DIAG") == "1"
    on_hold = None
    if diag:
        shot_base = f"/tmp/px_pre_{int(t0)}_{attempt}.png"
        await asyncio.to_thread(br.screenshot, shot_base, wid)

        def on_hold():
            br.screenshot(f"/tmp/px_mid_{int(t0)}_{attempt}.png", wid)

    await asyncio.to_thread(hand.press_and_hold, hold_s, bx, by, log.info, on_hold)
    _ph[f"hold{attempt}"] = time.time()
    await asyncio.to_thread(br.screenshot, f"/tmp/px_sessionless_{int(t0)}.png", wid)
    if diag:
        diff = await asyncio.to_thread(
            _shot_diff, shot_base, f"/tmp/px_mid_{int(t0)}_{attempt}.png")
        log.info("percobaan %d: press terdaftar? diff=%d piksel berubah", attempt, diff)


async def solve_perimeterx_sessionless(
    session_id: str = None,
    uuid: str = None,
    vid: str = None,
    app_id: str = None,
    proxy: str = None,
    timeout_s: int = 180,
    hold_s: float = 9.0,
    keep_profile: bool = False,
    challenge_url: str = None,
) -> dict:
    """Solve the caller's PX press-and-hold challenge and return its ``_px3``.

    challenge_url : the caller's challenge URL, used verbatim. Preferred input — it
                    carries the exact ``session_id`` PX expects (a dashed UUID from
                    ``challengeMetadata.challengeUrl``; a UAID yields a blank page).
    uuid / vid    : the caller's challenge identity. REQUIRED in practice: the wrapper
                    posts them into the challenge, which is what makes it render.
    proxy         : MUST be the exit IP the caller will replay from (_px3 is bound to it).
    """
    t0 = time.time()
    app_id = (app_id or DEFAULT_APP_ID).strip()
    # Penanda tahap: tanpa ini, satu solve yang melewati deadline terlihat seperti
    # "solver lambat" tanpa tahu tahap mana yang memakan waktu. Terukur sebelumnya: bot
    # membatalkan di `solverTimeout` dengan 408 saat solver masih di percobaan 3/4, dan
    # tidak ada cara mengetahui biaya tiap tahap.
    _ph = {"start": t0}
    log.info("sessionless recv: challenge_url=%s uuid=%s vid=%s app_id=%s",
             challenge_url, uuid, vid, app_id)
    if not challenge_url and not session_id:
        return _result(t0, {}, "", False, False,
                       error="challenge_url (or session_id) required")
    if not proxy:
        return _result(t0, {}, "", False, False,
                       error="proxy required: _px3 is bound to the exit IP")

    url = (challenge_url or "").strip() or build_iframe_url(app_id, session_id)
    profile = f"/tmp/px_sessionless_{os.getpid()}_{int(time.time())}"
    shutil.rmtree(profile, ignore_errors=True)

    wrap = _Wrapper(url, uuid, vid)
    br = Browser(profile, proxy=proxy)
    gate = actuated = False
    accepted = False
    ua = ""
    note = None
    try:
        async with solve_slot(), _x11_lock:
            # Catat IP keluar di AWAL solve. PX mengikat challenge ke IP, jadi kalau IP
            # berubah sebelum hold selesai, challenge dibuang tanpa vonis. Terukur pada
            # proxy seluler: idle 4 menit = IP stabil, tetapi selama solve (Chromium +
            # banyak koneksi) IP berganti 3x dalam 90 detik, tiap ganti didahului drop
            # 4-8 detik. Tanpa catatan ini kegagalan itu tampak seperti bug biomekanik.
            ip_before = await asyncio.to_thread(_egress_ip, proxy) if proxy else ""
            # Jalur TANPA CDP. Terukur berulang: dengan CDP aktif, halaman challenge
            # berhenti di state skeleton (pill abu-abu terisi + 3 titik loading, tanpa
            # teks) sehingga tombol press-and-hold tidak pernah ada; tanpa CDP tombol
            # asli render ("Accessible challenge" + "& HOLD"). Uji "CDP boleh aktif"
            # sebelumnya menipu: saat itu challenge_url memakai ID PALSU, jadi captcha.js
            # tidak dimuat sama sekali dan "rendered" palsu.
            #
            # Konsekuensi: _pxvid tidak bisa ditanam lewat CDP (cookie-nya httpOnly), dan
            # cookie harus dipanen dari postMessage wrapper. Caller tetap memakai vid-nya
            # sendiri saat risk/verify; PX mengaitkan token ke vid dari postMessage
            # "block" yang kita kirim, bukan ke _pxvid milik browser.
            await asyncio.to_thread(br.start, wrap.url, 17.0)
            _ph["browser_ready"] = time.time()
            ua = await asyncio.to_thread(_profile_ua, br)

            wid = await asyncio.to_thread(br.window_id)
            if not wid:
                return _result(t0, wrap.cookies, ua, False, False,
                               error="browser window not found",
                               events=len(wrap.events))

            deadline = time.time() + 30
            while time.time() < deadline and not wrap.rendered.is_set():
                await asyncio.sleep(1)
            _ph["gate"] = time.time()
            gate = wrap.rendered.is_set()
            if not gate:
                note = "challenge never reported 'rendered'"

            hand = Hand()
            # RETRY — PX menilai hold secara probabilistik, dan di UI asli hold yang gagal
            # menyisakan tombolnya untuk dicoba lagi (kadang 2-3x baru lolos). Terukur di
            # log event: setiap `failed` diikuti `_pxvid` BARU lalu `rendered` lagi, jadi
            # PX mereset visitor dan merender ulang challenge — peluang berikutnya memang
            # disediakan. Berhenti setelah satu percobaan membuang peluang itu.
            max_attempts = int(os.environ.get("PX_HOLD_ATTEMPTS", "4") or 4)
            # ANGGARAN WAKTU, bukan sekadar jumlah percobaan.
            #
            # Terukur: satu solve dengan 4 percobaan butuh ~345 s, sedangkan deadline
            # pemanggil 330 s — jadi server mengembalikan 408 dan TIDAK ADA hasil sama
            # sekali, sehingga laporan solver (dan diagnosis vonis PX) hilang. Retry harus
            # berhenti saat anggaran tinggal sedikit, lalu melaporkan apa yang sudah
            # didapat, alih-alih ditembak mati oleh deadline.
            budget_end = t0 + max(30.0, float(timeout_s) - 20.0)
            for attempt in range(1, max_attempts + 1):
                # Sisa waktu harus cukup untuk satu putaran penuh (deteksi + hold + jendela
                # vonis + tunggu render). Kalau tidak, lebih berguna mengembalikan hasil
                # sekarang daripada memulai percobaan yang pasti terpotong.
                _need = 8.0 + hold_s + 18.0 + 12.0 + 2.0
                if attempt > 1 and time.time() + _need > budget_end:
                    log.info("anggaran habis: berhenti di percobaan %d (sisa %.0fs, "
                             "butuh %.0fs)", attempt - 1, budget_end - time.time(), _need)
                    note = ((note + "; ") if note else "") + \
                        f"stopped at attempt {attempt - 1}/{max_attempts} (time budget)"
                    break
                # JANGAN clear `solved`: vonis PX bisa datang terlambat (setelah jendela
                # percobaan berakhir, saat kita menunggu render ulang). Terukur: produksi
                # menerima {"type":"succeeded"} 2x tapi solver melaporkan gagal, karena
                # clear() di awal percobaan berikutnya menghapus vonis yang sudah masuk.
                if wrap.solved.is_set():
                    accepted = True
                    log.info("hold DITERIMA (vonis datang sebelum percobaan %d)", attempt)
                    break
                wrap.failed.clear()
                wrap.rendered.clear()
                # Hanya tombol pill sejati yang punya tinggi band >= 20 px. Terukur:
                # detektor kadang mengembalikan band 2-3 px (tepi atas tombol) dan hold
                # yang mendarat di situ TIDAK terdaftar — percobaan berikutnya terbuang.
                # Kalau tidak terdeteksi dengan yakin, tunggu render ulang lalu cari lagi.
                for _try in range(3):
                    box = await asyncio.to_thread(_find_gate_button, br, wid, br.height)
                    # Pakai juga tinggi band yang SUDAH diukur `_find_gate_button`.
                    #
                    # `_band_height` mengambil screenshot BARU; kalau render sedang
                    # transisi, pengukuran ulang itu mengembalikan nilai tipis dan deteksi
                    # yang sebenarnya valid ikut dibuang — lalu jatuh ke fallback pusat
                    # jendela (640) yang terukur tidak pernah dinilai PX.
                    bh = getattr(br, "last_band_height", 0)
                    if box and (bh >= 14 or _band_height(br, wid) >= 14):
                        break
                    if box:
                        log.info("band tombol terlalu tipis (%d px) — tunggu render ulang",
                                 _band_height(br, wid))
                    box = None
                    await asyncio.sleep(2.5)
                if not box:
                    # Pakai deteksi bagus TERAKHIR dari sesi ini: tombol PX tidak berpindah
                    # antar percobaan, dan menyerah pada band tipis berarti hold tidak
                    # pernah mendarat di tombol sama sekali (terukur: 0 dari seluruh
                    # percobaan diterima PX karena ini).
                    prev = getattr(br, "last_good_button", None)
                    if prev:
                        box = prev
                        log.info("pakai koordinat tombol terakhir yang valid: (%d,%d)",
                                 prev[0], prev[1])
                if box:
                    bx, by = box
                elif attempt == 1:
                    # JANGAN pakai pusat jendela sebagai fallback.
                    #
                    # Terukur: `br.width // 2` = 640 mendarat di CELAH antara ikon
                    # accessibility dan pill, dan hold di situ tidak pernah dinilai PX
                    # (seluruh percobaan ditolak). Layout challenge PX tetap, dan pusat pill
                    # berada ~23 px di KANAN pusat jendela karena ikon duduk di kiri.
                    # Pakai koordinat valid terakhir bila ada; kalau tidak, geser dari
                    # pusat jendela sebesar offset terukur itu.
                    prev0 = getattr(br, "last_good_button", None)
                    if prev0:
                        bx, by = prev0
                        log.info("tombol tidak terdeteksi — pakai koordinat valid terakhir "
                                 "(%d,%d)", bx, by)
                    else:
                        bx, by = br.width // 2 + 23, 176
                        log.info("tombol tidak terdeteksi — pakai offset layout terukur "
                                 "(%d,%d), bukan pusat jendela", bx, by)
                    note = ((note + "; ") if note else "") + \
                        "button not located, used fallback"
                else:
                    # JANGAN berhenti di percobaan 2+. Layout challenge PX tetap, jadi
                    # koordinat tombol tidak berubah antar percobaan — dan percobaan
                    # ketiga sering yang lolos. Terukur: `break` di sini membuat solver
                    # hanya mencoba 2 kali ("MENOLAK hold 2 percobaan") padahal
                    # PX_HOLD_ATTEMPTS=3, sehingga peluang yang sudah dianggarkan hilang.
                    prev1 = getattr(br, "last_good_button", None)
                    if prev1:
                        bx, by = prev1
                    else:
                        bx, by = br.width // 2 + 23, 176
                    log.info("percobaan %d: tombol tidak terdeteksi lagi — pakai "
                             "koordinat layout (%d,%d)", attempt, bx, by)
                    note = ((note + "; ") if note else "") + \
                        f"attempt {attempt}: button not located, used layout position"
                log.info("hold percobaan %d/%d di (%d,%d)", attempt, max_attempts, bx, by)

                # ── JALUR A11Y: klik "Accessible challenge" lalu "Press again" ──
                #
                # Ini alur yang TERBUKTI dipakai repo LainsNL/OutlookRegister dan tidak
                # menahan tombol sama sekali:
                #     klik [aria-label="可访问性挑战"]  (Accessible challenge)
                #     klik [aria-label="再次按下"]      (Press again)
                # PX memperlakukan ini sebagai challenge alternatif, jadi tidak menilai
                # biomekanik hold — persis bagian yang selama ini menolak kita.
                #
                # Dijalankan SEBELUM jalur hold. Kalau ikonnya tidak ada atau alurnya
                # tidak menghasilkan vonis, kita jatuh ke hold biasa (jalur lama tetap
                # utuh sebagai cadangan).
                a11y_done = False
                if os.environ.get("PX_A11Y", "1") != "0":
                    icon = await asyncio.to_thread(_find_a11y_icon, br, wid, br.height)
                    if not icon:
                        # Deteksi gambar tidak selalu tersedia (di Xvfb ini Chromium
                        # tidak memetakan window-nya, jadi `import` gagal terus).
                        # Jangan lewati jalur a11y hanya karena itu: posisinya tetap —
                        # ikon duduk tepat 158 px di kiri pusat pill (terukur: ikon
                        # 505 vs pill 663, pada semua render). Pakai offset itu.
                        icon = (bx - 158, by)
                        log.info("a11y: ikon tidak terdeteksi — pakai offset layout "
                                 "(%d,%d) dari pusat pill (%d,%d)", icon[0], icon[1], bx, by)
                    if icon:
                        log.info("a11y: klik Accessible challenge di (%d,%d)", *icon)
                        await asyncio.to_thread(hand.click, icon[0], icon[1])
                        # Setelah ikon diklik, PX mengganti tombol menjadi spinner loading
                        # ("Press again" versi accessibility). Beri waktu transisinya.
                        await asyncio.sleep(random.uniform(0.9, 1.3))
                        pill = await asyncio.to_thread(_find_gate_button, br, wid, br.height)
                        if pill:
                            px_, py_ = pill
                        else:
                            # Spinner tidak terdeteksi sebagai pill (bentuknya berbeda),
                            # jadi pakai posisi tombol yang sudah diketahui dari deteksi
                            # awal percobaan ini — tombol tidak berpindah tempat.
                            px_, py_ = bx, by
                        log.info("a11y: klik Press again di (%d,%d)", px_, py_)
                        await asyncio.to_thread(hand.click, px_, py_)
                        a11y_done = True
                        await asyncio.to_thread(br.screenshot,
                                                f"/tmp/px_a11y_{int(t0)}.png", wid)
                    else:
                        log.info("a11y: ikon Accessible challenge tidak ditemukan — "
                                 "lanjut jalur hold")
                if a11y_done:
                    _ph[f"a11y{attempt}"] = time.time()
                    actuated = True
                    await asyncio.to_thread(br.screenshot,
                                            f"/tmp/px_sessionless_{int(t0)}.png", wid)
                    # ── Tunggu spinner SELESAI, jangan menilai terlalu cepat ──
                    #
                    # Repo LainsNL/OutlookRegister menunggu elemen `.draw` hilang sampai
                    # 14 detik sebelum memutuskan.
                    #
                    # PENTING — jangan pakai "ikon hilang" sebagai bukti lolos. Terukur:
                    # ikon accessibility JUGA hilang saat PX menolak, karena halaman
                    # dirender ulang (`rendered`) dan ikonnya sempat tidak ada. Menilai
                    # dari situ menghasilkan "a11y DITERIMA" padahal event-nya `failed`
                    # (0 succeeded / 2 failed pada uji). Satu-satunya bukti sah adalah
                    # event `succeeded` dari PX.
                    settled = await asyncio.to_thread(
                        _wait_a11y_gone, br, wid, br.height, 14.0)
                    log.info("a11y: ikon %s setelah tunggu 14 s",
                             "hilang" if settled else "masih ada")
                else:
                    await _do_hold(br, hand, wid, bx, by, hold_s, attempt, t0, _ph, log)
                    # WAJIB: tandai bahwa press benar-benar dilakukan.
                    #
                    # Tanpa baris ini `actuated` hanya pernah di-set di jalur a11y, sehingga
                    # saat ikon accessibility tidak ditemukan, hold yang BERHASIL pun
                    # dilaporkan `solved=false (press_hold_actuated=false)` karena
                    # solved = actuated and px3 and accepted. Terukur: satu sesi penuh
                    # menolak semua percobaan dengan pesan itu padahal `press-hold 9.0s`
                    # tercatat di log — jadi hold-nya jalan, tapi hasilnya dibuang.
                    actuated = True
                # Vonis PX untuk percobaan ini: "solved" = diterima, "failed" = ditolak.
                #
                # 18 s, bukan 40 s. Terukur: bot membatalkan request pada `solverTimeout`
                # (200 s) dengan 408 Request Timeout saat solver masih di percobaan 3/4,
                # sehingga seluruh hold tidak pernah dinilai. Anggaran tiap percobaan =
                # hold + jendela vonis + tunggu render; dengan jendela 40 s dan render 25 s
                # satu percobaan saja sudah ~70 s, jadi 4 percobaan mustahil selesai.
                # Vonis yang memang datang tiba dalam ~10 s; yang tidak datang tidak akan
                # datang karena menunggu lebih lama.
                px_deadline = time.time() + 18
                while time.time() < px_deadline:
                    if wrap.solved.is_set() or wrap.failed.is_set():
                        break
                    await asyncio.sleep(0.5)
                if wrap.solved.is_set():
                    accepted = True
                    log.info("hold DITERIMA pada percobaan %d/%d", attempt, max_attempts)
                    break
                # PENTING: vonis yang HILANG juga harus di-retry, bukan dianggap selesai.
                # Terukur: kasus paling umum adalah PX tidak mengirim `failed` maupun
                # `succeeded` sama sekali, dan kode yang `break` di sini hanya mencoba
                # SEKALI lalu menyerah — persis kelemahan "tidak ada retry" di UI asli,
                # di mana hold kadang perlu 2-3 percobaan.
                if wrap.failed.is_set():
                    log.info("percobaan %d ditolak PX (event failed)", attempt)
                else:
                    log.info("percobaan %d tanpa vonis PX — akan dicoba lagi", attempt)
                # PX menerbitkan _pxvid baru dan merender ulang; tunggu tombolnya siap
                # sebelum percobaan berikutnya, jangan menembak ke challenge lama.
                # 12 s, bukan 25 s — lihat catatan anggaran di jendela vonis di atas.
                # Jeda 0.5-1.0 s seperti repo LainsNL/OutlookRegister: PX butuh waktu
                # me-reset visitor sebelum challenge bisa diklik lagi.
                await asyncio.sleep(random.uniform(0.5, 1.0))
                rd = time.time() + 12
                while time.time() < rd and not wrap.rendered.is_set():
                    await asyncio.sleep(0.5)
                await asyncio.sleep(1.5)

            note_types = ",".join(sorted({str(e.get("data", {}).get("type"))
                                          for e in wrap.events
                                          if isinstance(e.get("data"), dict)}))
            log.info("sessionless events seen: %s (percobaan=%d)", note_types, attempt)
            if not accepted:
                # Jangan laporkan sukses: PX menolak semua hold, jadi `_px3` yang terbit
                # tidak akan diterima caller.
                log.warning("PX MENOLAK hold %d percobaan (event %r)", attempt,
                            wrap.failure_type)
                note = ((note + "; ") if note else "") + \
                    f"PX rejected {attempt} hold attempt(s) (event {wrap.failure_type!r})"
            if len(wrap.px3_history) > 1:
                log.info("_px3 berputar %d kali, memakai yang terakhir (len=%d)",
                         len(wrap.px3_history), len(wrap.px3_history[-1]))
            # IP sesudah solve: kalau berbeda dari ip_before, PX hampir pasti membuang
            # challenge di tengah jalan dan seluruh hold tidak dinilai. Ini penyebab yang
            # paling sering terukur pada proxy seluler, dan tanpa catatan ini kegagalannya
            # tampak seperti masalah biomekanik.
            ip_after = await asyncio.to_thread(_egress_ip, proxy) if proxy else ""
            if ip_before and ip_after and ip_before != ip_after:
                log.warning("IP BERGANTI saat solve: %s -> %s — challenge PX dibuang, "
                            "hold tidak dinilai", ip_before, ip_after)
                note = ((note + "; ") if note else "") + \
                    f"exit IP changed during solve ({ip_before} -> {ip_after})"
            elif not ip_after:
                log.warning("proxy mati saat solve (IP keluar tidak terbaca)")
                note = ((note + "; ") if note else "") + "proxy dropped during solve"
            await asyncio.sleep(3)
            # Cookie dipanen dari postMessage wrapper (jalur tanpa CDP). Jangan pakai
            # `_read_px_cookies_cdp` di sini: CDP tidak aktif di jalur ini.
            if not ua:
                ua = await asyncio.to_thread(_profile_ua, br)
    except Exception as e:                                          # noqa: BLE001
        log.warning("sessionless solve failed: %s", e)
        return _result(t0, wrap.cookies, ua, gate, actuated, error=str(e), note=note,
                       events=len(wrap.events), accepted=accepted)
    finally:
        await asyncio.to_thread(br.stop)
        wrap.close()
        if not keep_profile:
            shutil.rmtree(profile, ignore_errors=True)

    log.info("sessionless done: cookies=%s events=%d gate=%s actuated=%s",
             sorted(wrap.cookies), len(wrap.events), gate, actuated)
    # Rincian biaya waktu per tahap — dasar untuk mengatur deadline pemanggil. Tanpa ini,
    # menaikkan `PX_HOLD_ATTEMPTS` terlihat aman padahal totalnya melewati timeout bot.
    _prev = t0
    _parts = []
    for _k in sorted(_ph, key=lambda k: _ph[k]):
        _parts.append(f"{_k}=+{_ph[_k] - _prev:.1f}s")
        _prev = _ph[_k]
    log.info("durasi tahap: %s (total %.1fs)", " ".join(_parts), time.time() - t0)
    return _result(t0, wrap.cookies, ua, gate, actuated, note=note,
                   events=len(wrap.events), accepted=accepted)

def _free_port() -> int:
    """Port TCP kosong — CDP gagal naik kalau port masih terpakai sisa proses."""
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _seed_visitor_cdp(br: Browser, app_id: str, vid: str) -> bool:
    """Tanam `_pxvid` caller ke browser yang SEDANG berjalan (in-memory, langsung dipakai).

    Halaman challenge membaca window._pxVid dari cookie `_pxvid` (httpOnly — hanya CDP
    yang bisa menimpanya) atau localStorage <appId>_pxvid (base64 JSON {val:...}).
    Menanam di sesi yang sama menghindari kebutuhan persist ke disk, yang terukur tidak
    terjadi (Chromium meng-flush store sesuai jadwalnya sendiri, bukan saat SIGTERM).
    """
    try:
        br.cdp("Network.setCookie", {
            "name": "_pxvid", "value": vid, "domain": ".hsprotect.net", "path": "/",
            "secure": True, "httpOnly": True, "sameSite": "None",
            "expires": time.time() + 3600})
        payload = base64.b64encode(json.dumps({"val": vid}).encode()).decode()
        br.cdp("Runtime.evaluate", {
            "expression": (f"localStorage.setItem({json.dumps(app_id + '_pxvid')}, "
                           f"{json.dumps(payload)}); 1"),
            "returnByValue": True})
        got = _read_px_cookies_cdp(br).get("_pxvid")
        log.info("seed visitor: _pxvid=%s (cocok=%s)", got, got == vid)
        return got == vid
    except Exception as e:                                          # noqa: BLE001
        log.warning("seed visitor via CDP gagal: %s", e)
        return False


def _read_px_cookies_cdp(br: Browser) -> dict:
    """Baca cookie PX langsung dari browser yang sedang berjalan."""
    try:
        r = br.cdp("Network.getCookies", {"urls": ["https://iframe.hsprotect.net/"]})
        return {c["name"]: c.get("value") or ""
                for c in ((r.get("result") or {}).get("cookies") or [])}
    except Exception:
        return {}


def _cdp_ua(br: Browser) -> str:
    """UA browser yang sedang berjalan (untuk replay caller)."""
    try:
        r = br.cdp("Runtime.evaluate",
                   {"expression": "navigator.userAgent", "returnByValue": True})
        return ((r.get("result") or {}).get("result") or {}).get("value") or ""
    except Exception:
        return ""


def _profile_ua(br: Browser) -> str:
    """UA from the profile's Preferences (best effort; '' is acceptable)."""
    try:
        with open(os.path.join(br.profile, "Default", "Preferences")) as f:
            return (json.load(f) or {}).get("user_agent", "") or ""
    except Exception:
        return ""
