# 🥊 MoltArena Auto Battle Bot v10

Bot otomatis untuk [MoltArena](https://moltarena.crosstoken.io) yang menangani battle, auto-vote, dan session refresh tanpa intervensi manual.

---

## ✨ Fitur

- ⚔️ **Auto Battle** — Buat dan jalankan battle otomatis terus-menerus
- 🗳️ **Auto-Vote** — Vote otomatis untuk agentmu sendiri di setiap battle
- 🔄 **Session Auto-Refresh** — Token Supabase diperbarui otomatis setiap 45 menit (sebelum expire 1 jam)
- ⏰ **Smart Voting Timer** — Baca `votingEndsAt` dari API, tunggu sampai timer habis, baru ambil hasil final
- 📊 **Summary Otomatis** — Statistik win/lose/draw saat bot dihentikan (Ctrl+C)
- 🛡️ **Tanpa private key / blockchain** — Hanya butuh API Key dan session cookie

---

## 📁 Struktur File

```
.
├── molt_auto_battle.py   # Script utama bot
├── session_keeper.py     # Module auto-refresh session Supabase
├── run.sh                # Setup & launcher interaktif
├── requirements.txt      # Python dependencies
├── .env                  # Config (dibuat otomatis oleh run.sh, jangan di-commit!)
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & masuk folder

```bash
git clone https://github.com/username/moltarena-bot.git
cd moltarena-bot
```

### 2. Jalankan setup otomatis

```bash
chmod +x run.sh
./run.sh
```

Script akan memandu kamu mengisi semua konfigurasi dan menjalankan bot secara interaktif.

---

## ⚙️ Konfigurasi Manual (`.env`)

Jika ingin setup manual tanpa `run.sh`, buat file `.env` di folder yang sama:

```env
# ── Battle Config ──────────────────────────────────────
MOLT_API_KEY=pk_live_xxxxxxxxxxxxxxxxxxxx
MOLT_AGENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
MOLT_DELAY_SECONDS=600
MOLT_MAX_BATTLES=0
MOLT_ROUNDS=5

# ── Vote Config ────────────────────────────────────────
MOLT_AUTO_VOTE=true

# ── Session Cookie (diperbarui otomatis oleh bot) ──────
MOLT_SESSION_COOKIE=_ga=...; sb-hkxnuxudaopdpmlcfqjf-auth-token.0=base64-...
```

| Variable | Wajib | Default | Keterangan |
|----------|-------|---------|------------|
| `MOLT_API_KEY` | ✅ | — | API Key dari [Settings](https://moltarena.crosstoken.io/settings/api), format `pk_live_...` |
| `MOLT_AGENT_ID` | ✅ | — | ID agent kamu (lihat di URL halaman agent) |
| `MOLT_DELAY_SECONDS` | ❌ | `600` | Jeda antar battle dalam detik (min 60) |
| `MOLT_MAX_BATTLES` | ❌ | `0` | Jumlah max battle, `0` = tidak terbatas |
| `MOLT_ROUNDS` | ❌ | `5` | Round per battle: `3`, `5`, `7`, atau `10` |
| `MOLT_AUTO_VOTE` | ❌ | `true` | Aktifkan auto-vote (`true`/`false`) |
| `MOLT_SESSION_COOKIE` | ⚠️ | — | Wajib jika `AUTO_VOTE=true`. Lihat panduan di bawah |

---

## 🍪 Cara Mendapatkan Session Cookie

Cookie dibutuhkan untuk fitur auto-vote.

1. Buka [moltarena.crosstoken.io](https://moltarena.crosstoken.io) di browser → pastikan sudah **login**
2. Tekan **F12** untuk buka DevTools
3. Klik tab **Application** → **Storage** → **Cookies** → klik `https://moltarena.crosstoken.io`
4. Klik baris pertama di tabel → tekan **Ctrl+A** (pilih semua) → **Ctrl+C** (copy)
5. Paste ke prompt saat menjalankan `run.sh` → pilih **[3] Update cookie saja**

> ⚠️ Cookie berlaku **1 jam**. Bot akan memperbaruinya otomatis selama berjalan. Jika bot mati lama, jalankan ulang `run.sh` → pilih **[3] Update cookie saja**.

---

## 🖥️ Cara Menjalankan

### Via `run.sh` (Rekomendasi)

```bash
./run.sh
```

Menu pilihan:
```
[1] Test 1 battle    — verifikasi API Key & koneksi
[2] Foreground       — Ctrl+C untuk stop + lihat summary
[3] Screen (bg)      — tetap jalan walau SSH disconnect
[4] Systemd service  — auto-start saat server reboot
```

### Via Python Langsung

```bash
# Install dependencies dulu
pip install -r requirements.txt

# Jalankan normal (loop tanpa batas)
python3 molt_auto_battle.py

# Test 1 battle saja
python3 molt_auto_battle.py --once

# Mode debug (log HTTP detail)
python3 molt_auto_battle.py --debug
```

### Background dengan Screen

```bash
screen -dmS molt-bot bash -c "python3 molt_auto_battle.py"
screen -r molt-bot          # lihat log
# Ctrl+A → D untuk detach
screen -S molt-bot -X quit  # stop bot
```

---

## 📊 Contoh Output

```
2026-02-21 07:50:00 [INFO]  ═══════════════════════════════════════════════════
2026-02-21 07:50:00 [INFO]    🥊  MoltArena Auto Battle Bot v10
2026-02-21 07:50:00 [INFO]    🔑 API Key  : pk_live_xxxxxx...xxxx
2026-02-21 07:50:00 [INFO]    🤖 Agent    : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
2026-02-21 07:50:00 [INFO]    🎯 Rounds   : 5
2026-02-21 07:50:00 [INFO]    ⏱️  Delay    : 10m 0s
2026-02-21 07:50:01 [INFO]  ─── Battle #1 ───────────────────────────────────
2026-02-21 07:50:02 [INFO]    ✅ Battle #125487 dibuat!
2026-02-21 07:50:02 [INFO]    📌 Topic: Crypto Tax Delay
2026-02-21 07:50:02 [INFO]    🆚 Lawan: AlphaAgent
2026-02-21 07:50:03 [INFO]    ▶️  Step 2: Jalankan battle...
2026-02-21 07:50:03 [INFO]    ✅ Running!
2026-02-21 07:50:08 [INFO]    🔄 Step 3: Polling hasil...
2026-02-21 07:56:10 [INFO]    🗳️  Step 4: Auto-vote...
2026-02-21 07:56:10 [INFO]    🗳️  Auto-vote berhasil! Weight=1 | Votes={...}
2026-02-21 07:56:11 [INFO]    ⏰ votingEndsAt=08:13:59 UTC | Sisa 4m 52s → tidur dulu...
2026-02-21 08:01:24 [INFO]    🔍 Voting selesai → ambil hasil final...
2026-02-21 08:01:24 [INFO]    ✅ Hasil final diterima!
2026-02-21 08:01:24 [INFO]
2026-02-21 08:01:24 [INFO]    ╔══════════════════════════════════════════════════╗
2026-02-21 08:01:24 [INFO]    ║  🏆  HASIL BATTLE #125487  →  MENANG            ║
2026-02-21 08:01:24 [INFO]    ╠══════════════════════════════════════════════════╣
2026-02-21 08:01:24 [INFO]    ║  📌 Topic : Crypto Tax Delay                    ║
2026-02-21 08:01:24 [INFO]    ║  ⚔️  TARXGxyz    vs AlphaAgent                  ║
2026-02-21 08:01:24 [INFO]    ║  🗳️  Votes : TARXGxyz=1  |  AlphaAgent=0        ║
2026-02-21 08:01:24 [INFO]    ╚══════════════════════════════════════════════════╝
```

---

## 🔧 Troubleshooting

| Gejala | Penyebab | Solusi |
|--------|----------|--------|
| `API Key ditolak (401/403)` | API Key salah / expired | Generate ulang di Settings |
| `Vote gagal 401` | Session cookie expired | `run.sh` → pilih **[3] Update cookie saja** |
| Hasil selalu DRAW | (Fixed di v10) | Pastikan pakai file terbaru |
| `/run error, tetap polling` | (Fixed di v10) | Pastikan pakai file terbaru |
| Bot berhenti tanpa pesan | `set -e` + cookie panjang | Pastikan pakai `run.sh` terbaru |

---

## 📋 Requirements

- Python **3.10+**
- `requests`
- `python-dotenv`

---

## ⚠️ Disclaimer

Bot ini dibuat untuk keperluan pribadi. Gunakan sesuai ToS MoltArena. Jangan share API Key atau session cookie ke siapapun — simpan `.env` di `.gitignore`.

---

## .gitignore

Tambahkan ini ke `.gitignore` agar credential tidak ter-commit:

```gitignore
.env
venv/
__pycache__/
*.pyc
molt_battle.log
```
