# Rencana: solver self-hosted sebagai provider PX ke-3 di bot Go

## Yang tuan minta (koreksi arah)

Bot Go (`/root/outlook-request`) sudah berjalan dan **sudah** melakukan registrasi
Outlook sendiri lewat HTTP murni — bukan lewat browser. Provider captcha yang ada:
`captcha.run` dan **Offcaptcha**.

Yang kurang: satu provider lagi, yaitu **solver self-hosted kita**, khusus untuk
PerimeterX press-and-hold. Jadi:

- Solver = **provider solve**, dipanggil bot lewat `POST /solve`.
- Solver **bukan** alur registrasi. Renderer `outlook_signup` yang menjalankan form
  signup itu **salah arah** dan bukan deliverable.
- Kontraknya harus sama seperti Offcaptcha: bot mengirim identitas challenge-nya
  (`sessionId`/`uuid`/`vid`), solver menyelesaikan **challenge milik bot** itu, lalu
  mengembalikan `_px3`.

## Kontrak Offcaptcha yang harus ditiru (dari kode bot)

`pkg/solver/solver.go` mengirim task:

```json
{
  "type": "PXCaptchaSessionlessPressAndHold",
  "targetURL": "/api/v1.0/risk/verify",
  "sessionId": "<ctx.UAID>",
  "uuid": "<challengeMetadata.uuid>",
  "vid":  "<challengeMetadata.vid>"
}
```

Sumber nilai-nilai itu di bot (`pkg/protocol/risk.go`):

- `uuid` / `vid` → `risk/verify #1` → `challengeDetails.challengeMetadata.uuid|vid`
- `sessionId` → `ctx.UAID` (session id PX milik bot)
- `appId` → `challengeMetadata.appId`, fallback `PXzC5j78di` (`constants.go:19`)
- URL challenge yang sudah dihitung bot:
  `https://iframe.hsprotect.net/index.html?app_id=<appId>&session_id=<UAID>`

## Temuan terukur hari ini (dipakai untuk desain)

1. **Protokol otomasi mematikan gate.** Biner sama, IP sama:
   - dengan `--remote-debugging-*` (Playwright/CDP) → gate tidak pernah naik,
     `_px3` kosong, Microsoft membalas "Account creation has been blocked";
   - tanpa flag itu, dikendalikan X11 → gate naik, `_px3` terbit (675 byte).
   → Solver wajib pakai jalur X11, bukan CDP.
2. **`xdotool` ~7 Hz** (spawn proses tiap panggilan) vs sensor PX 60-125 Hz.
   `python-xlib` XTest mencapai ~2500 Hz → `tools/px_hand.py` (minimum-jerk,
   tremor fisiologis, 100 Hz).
3. **`_px3` TTL ~10 menit.** Rantai solve → panen → replay harus muat di jendela itu.
4. **Panen cookie di jalur X11**: store profil tidak bisa didekripsi manual
   (kunci custom CloakBrowser; ~400k kandidat gagal). Jalan yang berhasil: tutup
   browser dengan SIGTERM (bukan `kill -9`), lalu relaunch profil yang sama dengan
   `--remote-debugging-port` dan baca `Storage.getCookies` — browser mendekripsi
   store-nya sendiri. `tools/px_harvest.py` sudah terbukti mengembalikan `_pxvid`.
5. **Iframe challenge bisa dibuka langsung**: `iframe.hsprotect.net/index.html?app_id=…&session_id=…`
   memuat halaman berjudul "HUMAN Iframe Page". Dengan session_id palsu halamannya
   blank (butuh sesi nyata), tapi ini pintu masuk yang benar — **tanpa** alur signup.

## Langkah kerja

1. Tambah field di `SolveRequest` (server.py): `session_id`, `uuid`, `vid`, `app_id`,
   `target_url`, dan `mode` (`sessionless`).
2. Tambah `solve_perimeterx_sessionless(...)` di `perimeterx/solve.py`: buka iframe
   challenge dengan `app_id`/`session_id` milik caller, pakai jalur X11 + `px_hand`,
   panen cookie lewat `px_harvest`.
3. Ubah `SolvePerimeterXSelfHosted` (Go) supaya mengirim `uuid`/`vid`/`sessionId`/
   `appId` ke solver — bukan hanya `render_flow`.
4. Uji: bot Mode 3 (atau run kecil) → cek `_px3` yang dikembalikan diterima di
   `risk/verify #2`.
5. Renderer `outlook_signup` dipertahankan hanya sebagai alat diagnosa, bukan jalur
   produksi.

## Belum terbukti

- Apakah iframe dengan `session_id` nyata (dari bot) benar-benar merender gate dan
  menerbitkan `_px3` yang diterima `risk/verify #2`. Butuh satu sesi bot nyata untuk
  membuktikan; uji dengan session_id palsu hanya membuktikan halamannya memuat.
