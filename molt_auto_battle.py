#!/usr/bin/env python3
"""
MoltArena Auto Battle Bot — v10
================================
- API Key untuk battle
- Auto-Vote dengan Supabase session cookie
- Session auto-refresh setiap 45 menit (token expire 1 jam)
- Tanpa private key / blockchain
- Summary otomatis saat Ctrl+C
"""

import os, sys, time, json, logging, argparse, signal, importlib.util
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

BASE_URL = "https://moltarena.crosstoken.io"
API_BASE = f"{BASE_URL}/api"

# ─── Semua config dari .env ────────────────────────────────────
AGENT_ID       = os.getenv("MOLT_AGENT_ID",       "")
API_KEY        = os.getenv("MOLT_API_KEY",         "")
DELAY_SEC      = int(os.getenv("MOLT_DELAY_SECONDS", "600"))
MAX_BATTLES    = int(os.getenv("MOLT_MAX_BATTLES",   "0"))
ROUNDS         = int(os.getenv("MOLT_ROUNDS",        "5"))
AUTO_VOTE      = os.getenv("MOLT_AUTO_VOTE",         "true").lower() not in ("0","false","no")
SESSION_COOKIE = os.getenv("MOLT_SESSION_COOKIE",    "")

# ─── Session Stats ─────────────────────────────────────────────
stats = {
    "start_time": datetime.now(),
    "total":   0,
    "win":     0,
    "lose":    0,
    "draw":    0,
    "skip":    0,
    "voted":   0,
    "battles": [],
}

# ─── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "molt_battle.log",
            encoding="utf-8"
        ),
    ],
)
log = logging.getLogger("MoltBot")

# ─── Session Keeper (auto-refresh cookie) ─────────────────────
_keeper = None

def _init_session_keeper():
    global _keeper
    if not AUTO_VOTE or not SESSION_COOKIE:
        return
    try:
        script_dir = Path(__file__).parent
        spec = importlib.util.spec_from_file_location(
            "session_keeper", script_dir / "session_keeper.py"
        )
        if not spec:
            log.warning("  ⚠️  session_keeper.py tidak ditemukan di direktori bot")
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _keeper = mod.SessionKeeper(cookie_str=SESSION_COOKIE, env_path=ENV_PATH)
        _keeper.start()
    except Exception as e:
        log.error(f"  ❌ SessionKeeper init error: {e}")


# ─── HTTP Helpers ──────────────────────────────────────────────
def _h_auth() -> dict:
    return {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type":    "application/json",
        "authorization":   f"Bearer {API_KEY}",
        "origin":          BASE_URL,
        "referer":         f"{BASE_URL}/battles/new",
        "user-agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

def _h_noauth() -> dict:
    return {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin":          BASE_URL,
        "referer":         f"{BASE_URL}/battles/new",
        "user-agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", headers=_h_noauth(), timeout=30)
        if r.status_code == 200:
            return r.json()
        log.error(f"GET {path} → {r.status_code}: {r.text[:100]}")
        return None
    except Exception as e:
        log.error(f"GET {path} → {e}")
        return None

def api_post_auth(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", headers=_h_auth(), json=payload, timeout=30)
        log.debug(f"POST {path} → {r.status_code}")
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None

def api_post_noauth(path: str) -> dict | None:
    try:
        h = {**_h_noauth(), "content-length": "0"}
        r = requests.post(f"{API_BASE}{path}", headers=h, timeout=30)
        log.debug(f"POST {path} → {r.status_code}")
        if r.status_code in (200, 201):
            return r.json()
        return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
    except Exception as e:
        log.error(f"POST {path} → {e}")
        return None


# ─── Battle Steps ──────────────────────────────────────────────
def step1_create() -> dict | None:
    return api_post_auth("/deploy/battle", {
        "agent1Id":   AGENT_ID,
        "rounds":     ROUNDS,
        "language":   "en",
        "visibility": "public",
    })

def step2_run(battle_id: str) -> bool:
    """Jalankan battle — retry hingga 3x jika server error (500)."""
    cookie = _keeper.get_cookie() if _keeper else SESSION_COOKIE
    h = {
        "accept":           "*/*",
        "accept-language":  "en-US,en;q=0.9",
        "content-length":   "0",
        "origin":           BASE_URL,
        "referer":          f"{BASE_URL}/battles/new",
        "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
        "sec-ch-ua":        '"Not:A-Brand";v="99","Google Chrome";v="145"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest":   "empty",
        "sec-fetch-mode":   "cors",
        "sec-fetch-site":   "same-origin",
    }
    if cookie:
        h["cookie"] = cookie

    for attempt in range(1, 4):  # max 3x percobaan
        try:
            r = requests.post(f"{API_BASE}/battles/{battle_id}/run", headers=h, timeout=30)
            log.debug(f"  POST /run -> {r.status_code} (attempt {attempt})")
            if r.status_code in (200, 201):
                return True
            elif r.status_code == 500:
                log.warning(f"  /run HTTP 500 (attempt {attempt}/3): {r.text[:100]}")
                if attempt < 3:
                    wait = attempt * 10  # 10s, 20s
                    log.info(f"  ⏳ Retry /run dalam {wait}s...")
                    time.sleep(wait)
                    continue
            else:
                log.warning(f"  /run HTTP {r.status_code}: {r.text[:150]}")
                return False
        except Exception as e:
            log.warning(f"  /run error attempt {attempt}/3: {e}")
            if attempt < 3:
                time.sleep(10)
                continue
            return False

    log.warning("  ⚠️  /run gagal 3x — battle mungkin tetap berjalan, lanjut polling...")
    return False

def step3_poll(battle_id: str) -> dict | None:
    done = {"completed", "finished", "done", "ended", "voting"}
    elapsed, max_wait = 0, 300
    while elapsed < max_wait:
        time.sleep(15)
        elapsed += 15
        data = api_get(f"/battles/{battle_id}")
        if not data:
            continue
        battle = data.get("battle", data)
        status = str(battle.get("status", "")).lower()
        cur_r  = battle.get("currentRound", "?")
        log.info(f"  ⌛ [{status.upper()}] Round {cur_r}/{ROUNDS} | +{elapsed}s")
        if status in done:
            if status == "voting":
                log.info("  🗳️  Status VOTING → auto-vote...")
                step4_vote(battle_id, AGENT_ID)
            return battle
    return None

def step4_vote(battle_id: str, agent_id: str, _retry: bool = False) -> bool:
    if not AUTO_VOTE:
        return False
    cookie = _keeper.get_cookie() if _keeper else SESSION_COOKIE
    if not cookie:
        log.warning("  ⚠️  Vote dilewati: MOLT_SESSION_COOKIE belum diset")
        return False
    try:
        r = requests.post(
            f"{API_BASE}/battles/{battle_id}/vote",
            headers={
                "accept":           "*/*",
                "accept-language":  "en-US,en;q=0.9",
                "content-type":     "application/json",
                "origin":           BASE_URL,
                "referer":          f"{BASE_URL}/battles/new",
                "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36",
                "sec-ch-ua":        '"Not:A-Brand";v="99","Google Chrome";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-fetch-dest":   "empty",
                "sec-fetch-mode":   "cors",
                "sec-fetch-site":   "same-origin",
                "cookie":           cookie,
            },
            json={"agentId": agent_id},
            timeout=15,
        )
        if r.status_code in (200, 201):
            data   = r.json()
            weight = data.get("vote", {}).get("voteWeight", "?")
            counts = data.get("voteCounts", {})
            log.info(f"  🗳️  Auto-vote berhasil! Weight={weight} | Votes={counts}")
            stats["voted"] += 1
            return True
        elif r.status_code == 409:
            log.info("  🗳️  Sudah vote di battle ini (skip).")
            return False
        elif r.status_code == 401:
            if not _retry and _keeper:
                ok = _keeper.handle_401()
                if ok:
                    return step4_vote(battle_id, agent_id, _retry=True)
            elif not _retry:
                log.warning(
                    "  ❌ Vote 401 — session expired.\n"
                    "  📋 Jalankan ./run.sh → [2] Setup ulang config → ikuti panduan cookie"
                )
            return False
        else:
            log.warning(f"  ⚠️  Vote gagal HTTP {r.status_code}: {r.text[:150]}")
            return False
    except Exception as e:
        log.error(f"  Vote error: {e}")
        return False


# ─── Step 5: Tunggu Final Result setelah Voting ────────────────
def step5_wait_final(battle_id: str, voting_battle: dict | None = None) -> dict | None:
    """
    Tunggu server finalize result setelah timer voting habis.
    Fetch fresh API di awal untuk dapat votingEndsAt terbaru.
    """
    from datetime import timezone, datetime as _dt
    final_status = {"completed", "finished", "done", "ended"}

    # ── Fetch fresh data untuk dapat votingEndsAt terbaru ────
    fresh = api_get(f"/battles/{battle_id}")
    battle_data = (fresh.get("battle", fresh) if fresh else None) or voting_battle or {}

    # Cek apakah sudah completed saat step5 dimulai
    status_now = str(battle_data.get("status", "")).lower()
    if status_now in final_status and battle_data.get("winnerId"):
        log.info("  ✅ Battle sudah completed!")
        return battle_data

    # ── Hitung sisa waktu voting dari votingEndsAt ────────────
    wait_before_poll = 0
    voting_ends_str  = battle_data.get("votingEndsAt", "")

    if voting_ends_str:
        try:
            ends_at = _dt.fromisoformat(voting_ends_str.replace("Z", "+00:00"))
            now_utc = _dt.now(timezone.utc)
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            sisa = (ends_at - now_utc).total_seconds()
            wait_before_poll = max(0, sisa) + 25  # +25s buffer
            mins = int(wait_before_poll // 60)
            secs = int(wait_before_poll % 60)
            log.info(f"  ⏰ votingEndsAt={voting_ends_str[11:19]} UTC | Sisa {mins}m {secs}s → tidur dulu...")
        except Exception as e:
            log.debug(f"  Parse votingEndsAt error: {e} | val={voting_ends_str!r}")

    if wait_before_poll <= 0:
        # Fallback: estimasi 5m 20s dari sekarang (default voting timer MoltArena)
        wait_before_poll = 340
        log.info(f"  ⏳ votingEndsAt belum tersedia → estimasi {wait_before_poll//60}m {wait_before_poll%60}s...")

    # ── Tunggu dengan log progress tiap 60 detik ─────────────
    slept = 0
    while slept < wait_before_poll:
        chunk = min(60, wait_before_poll - slept)
        time.sleep(chunk)
        slept += chunk
        remaining = wait_before_poll - slept
        if remaining > 10:
            log.info(f"  ⏳ Voting berlangsung... {int(remaining)}s lagi")

    # ── Poll hasil — max 8 menit ──────────────────────────────
    log.info("  🔍 Voting selesai → ambil hasil final...")
    max_poll = 480
    elapsed  = 0
    while elapsed < max_poll:
        data = api_get(f"/battles/{battle_id}")
        if data:
            battle = data.get("battle", data)
            status = str(battle.get("status", "")).lower()
            winner = battle.get("winnerId")
            vote_a = battle.get("voteCountA", 0)
            vote_b = battle.get("voteCountB", 0)
            log.info(f"  ⌛ [{status.upper()}] winner={'✅' if winner else '⏳'} | votes={vote_a}:{vote_b} | +{elapsed}s")
            if winner is not None:
                log.info("  ✅ Hasil final diterima!")
                return battle
            if status in final_status:
                log.info("  ✅ Battle completed!")
                return battle
        time.sleep(15)
        elapsed += 15

    log.warning("  ⚠️  Timeout poll hasil — ambil data terakhir")
    data = api_get(f"/battles/{battle_id}")
    return data.get("battle", data) if data else None


# ─── Tampilkan Hasil ───────────────────────────────────────────
def show_result(battle: dict, my_id: str) -> str:
    if not battle:
        return "skip"
    agent_a   = battle.get("agentA") or {}
    agent_b   = battle.get("agentB") or {}
    name_a    = agent_a.get("name", "Agent A")
    name_b    = agent_b.get("name", "Agent B")
    id_a      = agent_a.get("id", "")
    winner_id = battle.get("winnerId")
    vote_a    = battle.get("voteCountA", 0)
    vote_b    = battle.get("voteCountB", 0)
    topic     = battle.get("topic", "?")
    bnum      = battle.get("battleNumber", "?")
    url       = f"{BASE_URL}/battle/{battle.get('id','?')}"

    my_name = name_a if my_id == id_a else name_b
    op_name = name_b if my_id == id_a else name_a
    my_vote = vote_a if my_id == id_a else vote_b
    op_vote = vote_b if my_id == id_a else vote_a

    if winner_id is None:
        outcome, icon, label = "draw", "🤝", "DRAW  "
    elif winner_id == my_id:
        outcome, icon, label = "win",  "🏆", "MENANG"
    else:
        outcome, icon, label = "lose", "💀", "KALAH "

    log.info("")
    log.info("  ╔══════════════════════════════════════════════════╗")
    log.info(f"  ║  {icon}  HASIL BATTLE #{bnum:<6}  →  {label}            ║")
    log.info("  ╠══════════════════════════════════════════════════╣")
    log.info(f"  ║  📌 Topic : {topic[:42]:<42}  ║")
    log.info(f"  ║  ⚔️  {my_name[:12]:<12} vs {op_name[:12]:<12}                   ║")
    log.info(f"  ║  🗳️  Votes : {my_name[:8]:<8}={my_vote}  |  {op_name[:8]:<8}={op_vote}            ║")
    log.info(f"  ║  🔗 {url[:46]:<46}  ║")
    log.info("  ╚══════════════════════════════════════════════════╝")
    log.info("")
    return outcome


# ─── Summary ───────────────────────────────────────────────────
def print_summary():
    elapsed = datetime.now() - stats["start_time"]
    h, rem  = divmod(int(elapsed.total_seconds()), 3600)
    m, s    = divmod(rem, 60)
    total   = stats["total"]
    win     = stats["win"]
    wr      = f"{win/total*100:.1f}%" if total else "N/A"
    log.info("")
    log.info("  ╔══════════════════════════════════════════════════╗")
    log.info("  ║            📊  SESSION SUMMARY                   ║")
    log.info("  ╠══════════════════════════════════════════════════╣")
    log.info(f"  ║  ⏱️  Durasi      : {h}j {m}m {s}s{'':<25}║")
    log.info(f"  ║  ⚔️  Total Battle: {total:<32}║")
    log.info(f"  ║  🏆 Menang      : {win:<32}║")
    log.info(f"  ║  💀 Kalah       : {stats['lose']:<32}║")
    log.info(f"  ║  🤝 Draw        : {stats['draw']:<32}║")
    log.info(f"  ║  ⏭️  Skip/Error  : {stats['skip']:<32}║")
    log.info(f"  ║  🗳️  Auto-Vote   : {stats['voted']:<32}║")
    log.info(f"  ║  📈 Win Rate    : {wr:<32}║")
    log.info("  ╠══════════════════════════════════════════════════╣")
    if stats["battles"]:
        log.info("  ║  📋 Riwayat (10 terakhir):                        ║")
        for b in stats["battles"][-10:]:
            ic = "🏆" if b["outcome"]=="win" else "💀" if b["outcome"]=="lose" else "🤝" if b["outcome"]=="draw" else "⏭️"
            log.info(f"  ║    {ic} #{b['num']:<6} vs {b['opponent'][:15]:<15} {b['outcome'].upper():<5}   ║")
    log.info("  ╚══════════════════════════════════════════════════╝")
    log.info("")


# ─── Countdown ─────────────────────────────────────────────────
def countdown(seconds: int):
    log.info(f"  ⏳ Cooldown {seconds//60}m {seconds%60}s...")
    end      = time.time() + seconds
    next_log = time.time() + 60
    while time.time() < end:
        time.sleep(1)
        if time.time() >= next_log:
            rem = int(end - time.time())
            log.info(f"  ⌛ Sisa cooldown: {rem//60}m {rem%60}s")
            next_log = time.time() + 60
    log.info("  ✅ Cooldown selesai!\n")


# ─── Validasi ──────────────────────────────────────────────────
def validate():
    errs = []
    if not AGENT_ID:
        errs.append("MOLT_AGENT_ID belum diset")
    if not API_KEY:
        errs.append("MOLT_API_KEY belum diset\n"
                    "  → moltarena.crosstoken.io/settings/api → Generate Key")
    elif not API_KEY.startswith("pk_live_"):
        errs.append("MOLT_API_KEY harus dimulai 'pk_live_'")
    for e in errs:
        log.error(f"❌ {e}")
    if errs:
        sys.exit(1)


# ─── Signal Handler ────────────────────────────────────────────
def _on_exit(sig, frame):
    log.info("\n⛔ Bot dihentikan\n")
    if _keeper:
        _keeper.stop()
    print_summary()
    sys.exit(0)


# ─── Main ──────────────────────────────────────────────────────
def main(max_override: int = None):
    max_b = max_override if max_override is not None else MAX_BATTLES

    signal.signal(signal.SIGINT,  _on_exit)
    signal.signal(signal.SIGTERM, _on_exit)

    sep = "═" * 58
    log.info(sep)
    log.info("  🥊  MoltArena Auto Battle Bot v10")
    log.info("  ─────────────────────────────────────────────────────")
    log.info(f"  🔑 API Key  : {API_KEY[:14]}...{API_KEY[-4:]}")
    log.info(f"  🤖 Agent    : {AGENT_ID}")
    log.info(f"  🎯 Rounds   : {ROUNDS}")
    log.info(f"  ⏱️  Delay    : {DELAY_SEC//60}m {DELAY_SEC%60}s")
    log.info(f"  🔄 Max      : {'∞ infinite' if max_b==0 else f'{max_b} battles'}")
    if AUTO_VOTE:
        if SESSION_COOKIE:
            log.info("  🗳️  Auto-Vote : ✅ Aktif — token refresh setiap 45 menit")
        else:
            log.info("  🗳️  Auto-Vote : ⚠️  Aktif tapi MOLT_SESSION_COOKIE belum diset")
    else:
        log.info("  🗳️  Auto-Vote : ❌ Nonaktif")
    log.info(sep + "\n")

    validate()
    stats["start_time"] = datetime.now()

    _init_session_keeper()

    log.info("🚀 Auto battle dimulai! (Ctrl+C untuk stop + lihat summary)\n")

    count = 0
    while True:
        count += 1
        stats["total"] = count
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log.info(f"{'─'*58}")
        log.info(f"  ⚔️  Battle ke-{count}  |  {now}")
        log.info(f"{'─'*58}")

        log.info("  📤 Step 1: Buat battle...")
        r1 = step1_create()

        if not r1 or r1.get("_error"):
            s    = (r1 or {}).get("_status", 0)
            body = (r1 or {}).get("_body", "")

            # Coba parse pesan error dari server
            server_msg = ""
            try:
                import json as _json
                err_data   = _json.loads(body)
                server_msg = (err_data.get("message") or err_data.get("error")
                              or err_data.get("detail") or "")
            except Exception:
                server_msg = body[:120] if body else ""

            if s in (401, 403):
                log.error(f"  ❌ API Key ditolak ({s}) → bot berhenti")
                print_summary(); sys.exit(1)
            elif s == 429:
                log.warning("  🚦 Rate limit → tunggu 5 menit...")
                stats["skip"] += 1; stats["total"] -= 1; count -= 1
                time.sleep(300); continue
            elif s == 400:
                log.warning(f"  ⚠️  Gagal buat battle (HTTP 400)")
                if server_msg:
                    log.warning(f"  📋 Pesan server: {server_msg}")

                # Deteksi apakah agent sedang dalam battle aktif
                busy_keywords = ("already", "active", "ongoing", "in progress",
                                 "sedang", "berlangsung", "cooldown", "busy",
                                 "pending", "running", "duplicate")
                is_busy = any(kw in server_msg.lower() for kw in busy_keywords)

                if is_busy:
                    wait_busy = 120  # tunggu 2 menit lalu retry
                    log.warning(f"  ⏳ Agent masih dalam battle aktif → tunggu {wait_busy}s lalu retry...")
                    stats["total"] -= 1; count -= 1
                    time.sleep(wait_busy); continue
                else:
                    log.warning("  ⏭️  Skipping → lanjut ke battle berikutnya")
                    stats["skip"] += 1
                    stats["battles"].append({"num":"?","opponent":"?","outcome":"skip"})
            else:
                log.warning(f"  ⚠️  Gagal buat battle (HTTP {s})")
                if server_msg:
                    log.warning(f"  📋 Pesan server: {server_msg}")
                stats["skip"] += 1
                stats["battles"].append({"num":"?","opponent":"?","outcome":"skip"})
        else:
            battle_raw = r1.get("battle", r1)
            battle_id  = battle_raw.get("id") or r1.get("battleId", "")
            bnum       = battle_raw.get("battleNumber", "?")
            topic      = battle_raw.get("topic", "?")
            agent_b    = (battle_raw.get("participants", {}).get("agent2") or
                          battle_raw.get("agentB") or {})
            opp_name   = agent_b.get("name", agent_b.get("displayName", "Random"))

            log.info(f"  ✅ Battle #{bnum} dibuat!")
            log.info(f"  📌 Topic: {topic}")
            log.info(f"  🆚 Lawan: {opp_name}")

            log.info("  ▶️  Step 2: Jalankan battle...")
            ok = step2_run(battle_id)
            log.info("  ✅ Running!" if ok else "  ⚠️  /run error, tetap polling...")

            log.info("  🔄 Step 3: Polling hasil...")
            time.sleep(5)
            result = step3_poll(battle_id)

            if result:
                status_now = str(result.get("status","")).lower()

                # Vote dulu jika masih di fase voting
                if status_now == "voting":
                    log.info("  🗳️  Step 4: Auto-vote...")
                    step4_vote(battle_id, AGENT_ID)
                    # Step 5: Tunggu hasil final — pakai votingEndsAt dari data battle
                    log.info("  🏁 Step 5: Tunggu hasil final...")
                    final = step5_wait_final(battle_id, voting_battle=result)
                    result = final if final else result
                else:
                    # Battle langsung selesai tanpa fase voting
                    log.info("  🗳️  Battle selesai → auto-vote...")
                    step4_vote(battle_id, AGENT_ID)

                outcome = show_result(result, AGENT_ID)
            else:
                log.warning("  ⚠️  Polling timeout")
                outcome = "skip"

            if outcome == "win":    stats["win"]  += 1
            elif outcome == "lose": stats["lose"] += 1
            elif outcome == "draw": stats["draw"] += 1
            else:                   stats["skip"] += 1

            stats["battles"].append({
                "num":      bnum,
                "opponent": opp_name,
                "outcome":  outcome,
            })

        if max_b > 0 and count >= max_b:
            log.info(f"\n✅ Target {max_b} battles tercapai.")
            break

        countdown(DELAY_SEC)

    print_summary()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="MoltArena Auto Battle Bot v10")
    p.add_argument("--once",  action="store_true", help="1 battle saja (test)")
    p.add_argument("--debug", action="store_true", help="Log HTTP detail")
    args = p.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    main(max_override=1 if args.once else None)
