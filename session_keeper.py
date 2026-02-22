#!/usr/bin/env python3
"""
session_keeper.py — Auto Session Refresh untuk MoltArena
=========================================================
MoltArena pakai Supabase auth. Token expire setiap 1 JAM.
Modul ini handle refresh otomatis tanpa blockchain/wallet.

Cara kerja:
  1. Parse refresh_token dari cookie sb-hkxnuxudaopdpmlcfqjf-auth-token
  2. Auto-discover Supabase anon key dari halaman MoltArena
  3. Setiap 45 menit: POST ke Supabase refresh endpoint
  4. Dapat access_token baru → rebuild cookie → simpan ke .env
  5. Vote tetap berjalan tanpa 401
"""

import os, re, sys, json, time, base64, logging, threading, requests
from pathlib import Path
from datetime import datetime

log = logging.getLogger("SessionKeeper")

BASE_URL         = "https://moltarena.crosstoken.io"
SUPABASE_PROJECT = "hkxnuxudaopdpmlcfqjf"
SUPABASE_URL     = f"https://{SUPABASE_PROJECT}.supabase.co"
AUTH_SESSION     = f"{BASE_URL}/api/auth/session"

REFRESH_INTERVAL = 45 * 60   # 45 menit — token expire 60 menit
MAX_COOKIE_CHUNK = 3000       # karakter per bagian cookie (.0 / .1)

SKIP_ATTR = {"path", "domain", "expires", "max-age", "samesite",
             "httponly", "secure", "priority", "version"}


class SessionKeeper:
    def __init__(self, cookie_str: str, env_path: str | Path = ".env"):
        self._cookie      = cookie_str.strip()
        self._env_path    = Path(env_path)
        self._lock        = threading.Lock()
        self._thread      = None
        self._running     = False
        self._last_ok     = None
        self._fail_cnt    = 0
        self._anon_key    = ""
        self._refresh_tok = ""
        self._ga_cookies  = {}
        self._parse_tokens()

    # ── PUBLIC ────────────────────────────────────────────────

    def start(self):
        if not self._cookie:
            log.warning("  ⚠️  SESSION_COOKIE kosong — auto-refresh tidak aktif")
            return

        valid, expiry = self._check_session()
        if valid:
            exp_str = expiry[:19].replace("T", " ") if expiry else "tidak diketahui"
            log.info(f"  ✅ Session valid! Expiry: {exp_str}")
        else:
            log.warning("  ⚠️  Session tidak valid → coba refresh...")
            self._do_refresh()

        if not self._anon_key:
            self._discover_anon_key()

        if self._refresh_tok:
            log.info(f"  🔑 Refresh token OK → auto-refresh setiap {REFRESH_INTERVAL//60} menit")
        else:
            log.warning("  ⚠️  Refresh token tidak ditemukan, pakai session ping saja")

        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="SessionKeeper")
        self._thread.start()

    def stop(self):
        self._running = False

    def get_cookie(self) -> str:
        with self._lock:
            return self._cookie

    def handle_401(self) -> bool:
        """Dipanggil saat vote 401 — refresh segera."""
        log.info("  🔄 Vote 401 → refresh session segera...")
        ok = self._do_refresh()
        if ok:
            log.info("  ✅ Session diperbarui! Vote akan dicoba ulang.")
            return True
        log.error(
            "\n  ❌ Refresh gagal — session expired total.\n"
            "  📋 Jalankan:  ./run.sh  → pilih [2] Setup ulang config → ikuti panduan cookie\n"
            "  ℹ️  Battle tetap berjalan, hanya auto-vote yang skip."
        )
        return False

    @property
    def status(self) -> str:
        if not self._cookie:
            return "❌ Tidak ada cookie"
        if self._last_ok:
            mins = int((datetime.now() - self._last_ok).total_seconds() / 60)
            return f"✅ Aktif (refresh {mins} menit lalu)"
        return "⏳ Belum pernah refresh"

    # ── PRIVATE LOOP ──────────────────────────────────────────

    def _loop(self):
        sleep_left = REFRESH_INTERVAL
        while self._running:
            time.sleep(1)
            sleep_left -= 1
            if sleep_left <= 0:
                self._do_refresh()
                sleep_left = REFRESH_INTERVAL

    # ── PRIVATE REFRESH ───────────────────────────────────────

    def _do_refresh(self) -> bool:
        # Prioritas 1: Supabase token refresh
        if self._refresh_tok:
            if not self._anon_key:
                self._discover_anon_key()
            if self._anon_key and self._supabase_refresh():
                return True

        # Prioritas 2: Session ping
        return self._session_ping()

    def _supabase_refresh(self) -> bool:
        try:
            r = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers={
                    "Content-Type": "application/json",
                    "apikey":       self._anon_key,
                },
                json={"refresh_token": self._refresh_tok},
                timeout=15,
            )
            log.debug(f"  [supabase refresh] → {r.status_code}")
            if r.status_code != 200:
                log.warning(f"  ⚠️  Supabase refresh gagal ({r.status_code}): {r.text[:80]}")
                return False

            data = r.json()
            new_access  = data.get("access_token", "")
            new_refresh = data.get("refresh_token", "")
            if not new_access:
                return False
            if new_refresh:
                self._refresh_tok = new_refresh

            new_cookie = self._rebuild_supabase_cookie(data)
            if new_cookie:
                with self._lock:
                    self._cookie = new_cookie
                self._save_to_env(new_cookie)
                self._last_ok  = datetime.now()
                self._fail_cnt = 0
                log.info(f"  🔄 Token Supabase diperbarui! ({datetime.now().strftime('%H:%M:%S')}) +1 jam")
                return True
        except Exception as e:
            log.error(f"  ❌ Supabase refresh error: {e}")
        return False

    def _session_ping(self) -> bool:
        try:
            r = requests.get(
                AUTH_SESSION,
                headers={
                    "Accept":          "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Origin":          BASE_URL,
                    "Referer":         BASE_URL + "/",
                    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                       "AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
                    "cookie":          self.get_cookie(),
                },
                timeout=15,
            )
            log.debug(f"  [session ping] → {r.status_code}")
            if r.status_code != 200:
                self._fail_cnt += 1
                return False
            data = r.json()
            if not (data.get("user") or data.get("expires")):
                self._fail_cnt += 1
                return False

            # Ambil Set-Cookie baru jika ada
            new_cookies = {}
            try:
                raw_sc = r.raw.headers.getlist("Set-Cookie")
            except Exception:
                raw_sc = []
            if not raw_sc:
                sc = r.headers.get("Set-Cookie", "")
                raw_sc = [sc] if sc else []
            for sc_line in raw_sc:
                name_val = sc_line.split(";")[0].strip()
                if "=" in name_val:
                    k, v = name_val.split("=", 1)
                    k = k.strip()
                    if k.lower() not in SKIP_ATTR:
                        new_cookies[k] = v.strip()
            if new_cookies:
                existing = self._parse_cookie_str(self.get_cookie())
                existing.update(new_cookies)
                new_str = "; ".join(f"{k}={v}" for k, v in existing.items())
                with self._lock:
                    self._cookie = new_str
                self._save_to_env(new_str)
                log.info(f"  🔄 Cookie diperbarui via session ping ({datetime.now().strftime('%H:%M:%S')})")

            self._last_ok  = datetime.now()
            self._fail_cnt = 0
            return True
        except Exception as e:
            self._fail_cnt += 1
            log.error(f"  ❌ Session ping error: {e}")
            return False

    # ── PRIVATE SUPABASE HELPERS ──────────────────────────────

    def _parse_tokens(self):
        """Ekstrak refresh_token dari cookie sb-auth-token."""
        cookies = self._parse_cookie_str(self._cookie)
        self._ga_cookies = {k: v for k, v in cookies.items() if k.startswith("_ga")}

        tok0 = cookies.get(f"sb-{SUPABASE_PROJECT}-auth-token.0", "")
        tok1 = cookies.get(f"sb-{SUPABASE_PROJECT}-auth-token.1", "")

        if not tok0:
            log.debug("  sb-auth-token.0 tidak ditemukan di cookie")
            return

        log.debug(f"  tok0 len={len(tok0)}, tok1 len={len(tok1)}")

        raw = (tok0 + tok1).removeprefix("base64-")
        log.debug(f"  raw base64 len={len(raw)}, mod4={len(raw) % 4}")

        try:
            # Fix: (4 - n % 4) % 4 agar tidak tambah 4 '=' saat n % 4 == 0
            padding_needed = (4 - len(raw) % 4) % 4
            padded = raw + "=" * padding_needed

            # Coba decode normal dulu
            try:
                decoded = base64.b64decode(padded).decode("utf-8")
            except Exception:
                # Fallback: ignore invalid chars (toleran terhadap data korup)
                decoded = base64.b64decode(padded + "==", validate=False).decode("utf-8", errors="ignore")

            data = json.loads(decoded)
            self._refresh_tok = data.get("refresh_token", "")
            if self._refresh_tok:
                log.debug(f"  Refresh token: {self._refresh_tok[:8]}...")
            else:
                log.debug("  refresh_token key tidak ada di decoded JSON")
        except json.JSONDecodeError as e:
            log.debug(f"  JSON decode error: {e} (raw len={len(raw)})")
        except Exception as e:
            log.debug(f"  Parse token error: {e}")

    def _discover_anon_key(self):
        """Cari Supabase anon key dari JavaScript bundle MoltArena."""
        if self._anon_key:
            return
        log.debug("  🔍 Mencari Supabase anon key...")
        try:
            r = requests.get(BASE_URL, timeout=15,
                             headers={"User-Agent": "Mozilla/5.0 Chrome/145"})
            pattern = re.compile(
                r'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.'
                r'[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'
            )
            for m in pattern.finditer(r.text):
                jwt = m.group(0)
                parts = jwt.split(".")
                if len(parts) != 3:
                    continue
                try:
                    payload = json.loads(base64.b64decode(parts[1] + "==").decode())
                    if payload.get("role") == "anon" and payload.get("iss") == "supabase":
                        self._anon_key = jwt
                        log.info(f"  ✅ Supabase anon key ditemukan!")
                        return
                except Exception:
                    continue
            log.warning("  ⚠️  Supabase anon key tidak ditemukan — hanya session ping yang aktif")
        except Exception as e:
            log.debug(f"  Discover anon key error: {e}")

    def _rebuild_supabase_cookie(self, token_data: dict) -> str:
        """Encode token_data sebagai base64-JSON, split ke .0/.1, gabung dengan GA cookies."""
        try:
            encoded = "base64-" + base64.b64encode(
                json.dumps(token_data, separators=(",", ":")).encode()
            ).decode().rstrip("=")

            tok0 = encoded[:MAX_COOKIE_CHUNK]
            tok1 = encoded[MAX_COOKIE_CHUNK:]

            parts = [f"{k}={v}" for k, v in self._ga_cookies.items()]
            parts.append(f"sb-{SUPABASE_PROJECT}-auth-token.0={tok0}")
            if tok1:
                parts.append(f"sb-{SUPABASE_PROJECT}-auth-token.1={tok1}")
            return "; ".join(parts)
        except Exception as e:
            log.error(f"  ❌ Rebuild cookie error: {e}")
            return ""

    # ── PRIVATE HELPERS ───────────────────────────────────────

    def _check_session(self) -> tuple[bool, str]:
        try:
            r = requests.get(
                AUTH_SESSION,
                headers={
                    "cookie":     self.get_cookie(),
                    "Accept":     "application/json",
                    "User-Agent": "Mozilla/5.0 Chrome/145",
                    "Origin":     BASE_URL,
                    "Referer":    BASE_URL + "/",
                },
                timeout=10,
            )
            if r.status_code == 200:
                data   = r.json()
                expiry = data.get("expires", "")
                if data.get("user") or expiry:
                    return True, expiry
            return False, ""
        except Exception:
            return False, ""

    def _parse_cookie_str(self, cookie_str: str) -> dict:
        result = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            k = k.strip()
            if k.lower() not in SKIP_ATTR:
                result[k] = v.strip()
        return result

    def _save_to_env(self, cookie_str: str):
        try:
            if self._env_path.exists():
                text = self._env_path.read_text(encoding="utf-8")
                if "MOLT_SESSION_COOKIE=" in text:
                    # Ganti baris (tangani baik yang pakai quotes maupun tidak)
                    text = re.sub(
                        r'^MOLT_SESSION_COOKIE=.*$',
                        f'MOLT_SESSION_COOKIE="{cookie_str}"',
                        text, flags=re.MULTILINE,
                    )
                else:
                    text += f'\nMOLT_SESSION_COOKIE="{cookie_str}"\n'
            else:
                text = f'MOLT_SESSION_COOKIE="{cookie_str}"\n'
            self._env_path.write_text(text, encoding="utf-8")
        except Exception as e:
            log.error(f"  Gagal simpan cookie ke .env: {e}")


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")
    load_dotenv()
    cookie = os.getenv("MOLT_SESSION_COOKIE", "")
    if not cookie:
        print("❌ Set MOLT_SESSION_COOKIE di .env dulu")
        sys.exit(1)

    print("\n🧪 Test SessionKeeper...\n")
    keeper = SessionKeeper(cookie_str=cookie)
    keeper.start()
    time.sleep(5)
    print(f"\nStatus : {keeper.status}")
    print(f"Cookie : {keeper.get_cookie()[:80]}...")
    keeper.stop()
