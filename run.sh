#!/bin/bash
# MoltArena Auto Battle Bot v10 — Setup & Run
# Semua konfigurasi dilakukan di awal sebelum bot berjalan
set -e

# ── Warna ──────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BLUE='\033[0;34m'; BOLD='\033[1m'
DIM='\033[2m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
MAIN_SCRIPT="$SCRIPT_DIR/molt_auto_battle.py"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/molt_battle.log"

# ── Fungsi UI ──────────────────────────────────────────────────
info()    { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
success() { echo -e "  ${GREEN}✅ $1${NC}"; }
warn()    { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
error()   { echo -e "  ${RED}❌ $1${NC}"; }
step()    { echo -e "\n${BOLD}${BLUE}━━  $1${NC}"; }
line()    { echo -e "${DIM}  ──────────────────────────────────────────────────${NC}"; }
blank()   { echo ""; }

# ══════════════════════════════════════════════════════════════
print_banner() {
    clear 2>/dev/null || true
    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║       🥊   MoltArena Auto Battle Bot v10   🥊            ║${NC}"
    echo -e "${CYAN}${BOLD}║   Battle Otomatis │ Auto-Vote │ Session Auto-Refresh     ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ══════════════════════════════════════════════════════════════
check_python() {
    step "Cek Python..."
    if command -v python3 &>/dev/null; then
        success "$(python3 --version)"
        PYTHON_BIN="python3"
    else
        error "Python3 tidak ditemukan!"
        echo -e "  Install: ${YELLOW}sudo apt install python3 python3-pip python3-venv -y${NC}"
        exit 1
    fi
}

setup_venv() {
    step "Setup Virtual Environment..."
    [ ! -d "$VENV_DIR" ] && $PYTHON_BIN -m venv "$VENV_DIR" && info "venv baru dibuat"
    source "$VENV_DIR/bin/activate"
    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"
    success "Virtual environment siap"
}

install_deps() {
    step "Install Dependencies..."
    $PIP_BIN install -q --upgrade pip
    $PIP_BIN install -q requests python-dotenv
    success "Dependencies siap"
}

# ══════════════════════════════════════════════════════════════
# FUNGSI PARSE COOKIE (Python inline)
# Menerima format tabel DevTools ATAU format cookie biasa
# ══════════════════════════════════════════════════════════════
parse_cookie() {
    local raw_input="$1"
    $PYTHON_BIN - <<PYEOF
import sys, re

raw = """${raw_input}"""

SKIP_ATTR = {"path","domain","expires","max-age","samesite","httponly","secure",
             "priority","version","size","session","lax","strict","none",
             "medium","high","low","hostonly","httponly","samesite"}

cookies = {}

# ── Deteksi format ─────────────────────────────────────────
# Format tabel DevTools: ada kolom tab-separated (Name \t Value \t Domain ...)
# Format cookie biasa: name=value; name2=value2

lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]

is_table = any('\t' in line for line in lines)

if is_table:
    # Parse format tabel DevTools
    # Kolom: Name \t Value \t Domain \t Path \t Expires \t Size \t ... \t SameSite
    for line in lines:
        if not line or '\t' not in line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            name  = parts[0].strip()
            value = parts[1].strip()
            # Validasi nama cookie (bukan header kolom)
            if name and value and name.lower() not in SKIP_ATTR:
                # Skip baris header jika ada
                if name.lower() in ("name","cookie","key"):
                    continue
                cookies[name] = value
else:
    # Parse format cookie biasa: name=value; name2=value2
    for part in raw.replace('\n',' ').split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        k, v = part.split('=', 1)
        k = k.strip()
        v = v.strip()
        if k.lower() not in SKIP_ATTR:
            cookies[k] = v

if not cookies:
    print("ERROR: Tidak ada cookie yang berhasil di-parse", file=sys.stderr)
    sys.exit(1)

# Cek apakah token Supabase ada
sb_project = "hkxnuxudaopdpmlcfqjf"
has_token = any(f"sb-{sb_project}-auth-token" in k for k in cookies)
if not has_token:
    print("WARN: sb-auth-token tidak ditemukan di cookie", file=sys.stderr)

# Output cookie string
result = "; ".join(f"{k}={v}" for k, v in cookies.items())
print(result)
PYEOF
}

validate_cookie() {
    local cookie="$1"
    echo "$cookie" | grep -q "sb-hkxnuxudaopdpmlcfqjf-auth-token" && return 0 || return 1
}

# ══════════════════════════════════════════════════════════════
# SETUP KONFIGURASI LENGKAP
# ══════════════════════════════════════════════════════════════
run_full_setup() {
    print_banner

    echo -e "${BOLD}${CYAN}  📋  SETUP KONFIGURASI — Isi semua di bawah ini${NC}"
    echo ""
    echo -e "${DIM}  Semua nilai akan disimpan ke .env dan tidak perlu diisi ulang${NC}"
    line

    # ──────────────────────────────────────────────────────────
    blank
    echo -e "  ${BOLD}[1/6] 🔑 API KEY${NC}"
    echo -e "  ${DIM}Buka: https://moltarena.crosstoken.io/settings/api${NC}"
    echo -e "  ${DIM}Klik 'Generate API Key' → copy key yang dimulai pk_live_...${NC}"
    blank
    while true; do
        echo -ne "  Paste API Key: "
        read -r INPUT_APIKEY
        INPUT_APIKEY=$(echo "$INPUT_APIKEY" | tr -d '[:space:]')
        if [[ "$INPUT_APIKEY" == pk_live_* ]] && [ ${#INPUT_APIKEY} -gt 15 ]; then
            success "API Key valid ✓"
            break
        else
            warn "Harus dimulai 'pk_live_'. Coba lagi."
        fi
    done

    # ──────────────────────────────────────────────────────────
    blank; line; blank
    echo -e "  ${BOLD}[2/6] 🤖 AGENT ID${NC}"
    echo -e "  ${DIM}Buka halaman agent kamu → lihat URL:${NC}"
    echo -e "  ${DIM}moltarena.crosstoken.io/agents/${CYAN}AGENT-ID-DI-SINI${DIM}${NC}"
    blank
    while true; do
        echo -ne "  Paste Agent ID: "
        read -r INPUT_AGENT
        INPUT_AGENT=$(echo "$INPUT_AGENT" | tr -d '[:space:]')
        [ -n "$INPUT_AGENT" ] && { success "Agent ID: $INPUT_AGENT"; break; } \
            || warn "Tidak boleh kosong."
    done

    # ──────────────────────────────────────────────────────────
    blank; line; blank
    echo -e "  ${BOLD}[3/6] ⏱️  DELAY ANTAR BATTLE${NC}"
    echo -e "  ${DIM}Rekomendasi: 600 (10 menit) | Minimum: 60 (1 menit)${NC}"
    blank
    echo -ne "  Delay dalam detik [default 600]: "
    read -r INPUT_DELAY
    INPUT_DELAY=$(echo "$INPUT_DELAY" | tr -d '[:space:]')
    [[ "$INPUT_DELAY" =~ ^[0-9]+$ ]] || INPUT_DELAY=600
    info "Delay: ${INPUT_DELAY}s = $(( INPUT_DELAY / 60 )) menit $(( INPUT_DELAY % 60 )) detik"

    # ──────────────────────────────────────────────────────────
    blank; line; blank
    echo -e "  ${BOLD}[4/6] 🔄 JUMLAH BATTLE${NC}"
    blank
    echo -ne "  Max battle [0 = tidak terbatas]: "
    read -r INPUT_MAX
    INPUT_MAX=$(echo "$INPUT_MAX" | tr -d '[:space:]')
    [[ "$INPUT_MAX" =~ ^[0-9]+$ ]] || INPUT_MAX=0
    [ "$INPUT_MAX" -eq 0 ] && info "Mode: ∞ tanpa batas" || info "Berhenti setelah $INPUT_MAX battles"

    echo -ne "  Round per battle [3/5/7/10, default 5]: "
    read -r INPUT_ROUNDS
    INPUT_ROUNDS=$(echo "$INPUT_ROUNDS" | tr -d '[:space:]')
    [[ "$INPUT_ROUNDS" =~ ^(3|5|7|10)$ ]] || INPUT_ROUNDS=5
    info "Rounds: $INPUT_ROUNDS per battle"

    # ──────────────────────────────────────────────────────────
    blank; line; blank
    echo -e "  ${BOLD}[5/6] 🗳️  AUTO-VOTE${NC}"
    echo -e "  ${DIM}Vote otomatis untuk agentmu sendiri di setiap battle${NC}"
    blank
    echo -ne "  Aktifkan auto-vote? [Y/n]: "
    read -r INPUT_VOTE
    INPUT_VOTE=$(echo "$INPUT_VOTE" | tr -d '[:space:]')
    [[ "$INPUT_VOTE" =~ ^[Nn]$ ]] && INPUT_VOTE="false" || INPUT_VOTE="true"

    INPUT_COOKIE=""
    if [ "$INPUT_VOTE" = "true" ]; then
        # ──────────────────────────────────────────────────────
        blank; line; blank
        echo -e "  ${BOLD}[6/6] 🍪 SESSION COOKIE${NC}"
        blank
        echo -e "  ${YELLOW}${BOLD}  Panduan Langkah demi Langkah:${NC}"
        blank
        echo -e "  ${BOLD}  Langkah 1.${NC} Buka browser → ${CYAN}https://moltarena.crosstoken.io${NC}"
        echo -e "  ${BOLD}  Langkah 2.${NC} Pastikan sudah ${GREEN}LOGIN${NC}"
        echo -e "  ${BOLD}  Langkah 3.${NC} Tekan ${BOLD}F12${NC} untuk buka DevTools"
        echo -e "  ${BOLD}  Langkah 4.${NC} Klik tab ${BOLD}\"Application\"${NC} (atau \"Storage\" di Firefox)"
        echo -e "  ${BOLD}  Langkah 5.${NC} Di panel kiri: ${DIM}Storage${NC} → ${DIM}Cookies${NC} → klik:"
        echo -e "             ${CYAN}https://moltarena.crosstoken.io${NC}"
        echo -e "  ${BOLD}  Langkah 6.${NC} Kamu akan lihat daftar cookie seperti ini:"
        blank
        echo -e "  ${DIM}  ┌─────────────────────────────────────────────┬────────────┐${NC}"
        echo -e "  ${DIM}  │ Name                                        │ Value      │${NC}"
        echo -e "  ${DIM}  ├─────────────────────────────────────────────┼────────────┤${NC}"
        echo -e "  ${DIM}  │ _ga                                         │ GA1.1...   │${NC}"
        echo -e "  ${DIM}  │ _ga_XXXXX                                   │ GS2.1...   │${NC}"
        echo -e "  ${YELLOW}  ${BOLD}│ sb-hkxnuxudaopdpmlcfqjf-auth-token.0   ← INI!│ base64-... │${NC}"
        echo -e "  ${YELLOW}  ${BOLD}│ sb-hkxnuxudaopdpmlcfqjf-auth-token.1   ← INI!│ DJlZT...   │${NC}"
        echo -e "  ${DIM}  └─────────────────────────────────────────────┴────────────┘${NC}"
        blank
        echo -e "  ${BOLD}  Langkah 7.${NC} Pilih semua baris: klik baris pertama → ${BOLD}Ctrl+A${NC}"
        echo -e "  ${BOLD}  Langkah 8.${NC} Copy: ${BOLD}Ctrl+C${NC}"
        echo -e "  ${BOLD}  Langkah 9.${NC} Klik di bawah ini lalu ${BOLD}Ctrl+V${NC} (paste),"
        echo -e "             lalu tekan ${BOLD}Enter${NC} satu kali, lalu ${BOLD}Ctrl+D${NC} untuk selesai:"
        blank
        line

        # Baca input multi-line (user paste lalu Ctrl+D)
        RAW_COOKIE=""
        while IFS= read -r cookie_line; do
            RAW_COOKIE="${RAW_COOKIE}${cookie_line}
"
        done

        line
        blank

        if [ -z "$(echo "$RAW_COOKIE" | tr -d '[:space:]')" ]; then
            warn "Cookie kosong — auto-vote dinonaktifkan sementara"
            INPUT_VOTE="false"
        else
            # Parse cookie dengan Python
            PARSED=$(parse_cookie "$RAW_COOKIE" 2>/tmp/cookie_parse_err || true)
            PARSE_ERR=$(cat /tmp/cookie_parse_err 2>/dev/null || true)

            if [ -z "$PARSED" ]; then
                warn "Gagal parse cookie: $PARSE_ERR"
                warn "Auto-vote dinonaktifkan — bisa diisi manual di .env nanti"
                INPUT_VOTE="false"
            else
                INPUT_COOKIE="$PARSED"
                # Cek apakah token penting ada
                if echo "$INPUT_COOKIE" | grep -q "sb-hkxnuxudaopdpmlcfqjf-auth-token"; then
                    success "Cookie valid! Token Supabase ditemukan ✓"
                    info "Auto-refresh otomatis setiap 45 menit (token expire 1 jam)"
                else
                    warn "Token sb-auth-token tidak ditemukan di cookie kamu"
                    warn "Pastikan kamu sudah LOGIN dan copy cookie yang benar"
                    echo -ne "  Lanjutkan dengan cookie ini? [y/N]: "
                    read -r CONT
                    [[ "$CONT" =~ ^[Yy]$ ]] || { INPUT_COOKIE=""; INPUT_VOTE="false"; warn "Cookie dilewati"; }
                fi
            fi
        fi
    else
        blank; line
        info "[6/6] Cookie dilewati (auto-vote tidak aktif)"
    fi

    # ──────────────────────────────────────────────────────────
    # Tulis .env
    # ──────────────────────────────────────────────────────────
    blank; line
    cat > "$ENV_FILE" <<ENVEOF
# MoltArena Auto Battle Bot v10
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
# Jangan share file ini ke siapapun!
# ══════════════════════════════

# ── Battle Config ──────────────────────────────────────────
MOLT_API_KEY=${INPUT_APIKEY}
MOLT_AGENT_ID=${INPUT_AGENT}
MOLT_DELAY_SECONDS=${INPUT_DELAY}
MOLT_MAX_BATTLES=${INPUT_MAX}
MOLT_ROUNDS=${INPUT_ROUNDS}

# ── Vote Config ────────────────────────────────────────────
MOLT_AUTO_VOTE=${INPUT_VOTE}

# ── Session Cookie (auto-refresh setiap 45 menit) ──────────
# Diperbarui otomatis oleh bot — jangan edit manual saat bot berjalan
MOLT_SESSION_COOKIE=${INPUT_COOKIE}
ENVEOF

    success ".env berhasil dibuat!"
}

# ══════════════════════════════════════════════════════════════
show_config() {
    set -a; source "$ENV_FILE" 2>/dev/null; set +a
    blank
    echo -e "${BOLD}${CYAN}  📋  Konfigurasi Aktif:${NC}"
    line
    MASKED_KEY="${MOLT_API_KEY:0:14}...${MOLT_API_KEY: -4}"
    echo -e "  🔑 API Key   : ${GREEN}${MASKED_KEY}${NC}"
    echo -e "  🤖 Agent     : ${CYAN}${MOLT_AGENT_ID}${NC}"
    echo -e "  🎯 Rounds    : ${CYAN}${MOLT_ROUNDS:-5}${NC}"
    echo -e "  ⏱️  Delay     : ${CYAN}${MOLT_DELAY_SECONDS:-600}s ($(( ${MOLT_DELAY_SECONDS:-600} / 60 )) menit)${NC}"
    [ "${MOLT_MAX_BATTLES:-0}" -eq 0 ] \
        && echo -e "  🔄 Mode      : ${CYAN}∞ Tanpa batas${NC}" \
        || echo -e "  🔄 Max       : ${CYAN}${MOLT_MAX_BATTLES} battles${NC}"
    if [ "${MOLT_AUTO_VOTE:-true}" = "true" ]; then
        if [ -n "${MOLT_SESSION_COOKIE}" ]; then
            echo -e "  🗳️  Auto-Vote : ${GREEN}✅ Aktif — refresh setiap 45 menit${NC}"
            echo -e "  🍪 Cookie    : ${GREEN}${MOLT_SESSION_COOKIE:0:30}...${NC}"
        else
            echo -e "  🗳️  Auto-Vote : ${YELLOW}⚠️  Aktif tapi cookie belum diset${NC}"
        fi
    else
        echo -e "  🗳️  Auto-Vote : ${RED}❌ Nonaktif${NC}"
    fi
    line
    blank
}

# ══════════════════════════════════════════════════════════════
menu_env_ada() {
    blank
    echo -e "  ${BOLD}⚙️  File .env sudah ada. Apa yang ingin kamu lakukan?${NC}"
    blank
    echo -e "  ${CYAN}[1]${NC} Langsung jalankan bot"
    echo -e "  ${CYAN}[2]${NC} Setup ulang semua config dari awal"
    echo -e "  ${CYAN}[3]${NC} Update cookie saja (token expired)"
    echo -e "  ${CYAN}[4]${NC} Lihat config aktif"
    echo -e "  ${CYAN}[5]${NC} Keluar"
    blank
    echo -ne "  ${BOLD}Pilih [1-5]: ${NC}"
    read -r C
    case "$C" in
        1) return ;;
        2) rm -f "$ENV_FILE"; run_full_setup ;;
        3) update_cookie_only ;;
        4) show_config
           echo -ne "  Lanjut jalankan? [Y/n]: "
           read -r X; [[ "$X" =~ ^[Nn]$ ]] && exit 0 || return ;;
        5) exit 0 ;;
        *) return ;;
    esac
}

update_cookie_only() {
    blank
    set -a; source "$ENV_FILE" 2>/dev/null; set +a
    echo -e "  ${BOLD}🍪 Update Cookie${NC}"
    blank
    echo -e "  ${YELLOW}Token Supabase expire setiap 1 JAM.${NC}"
    echo -e "  ${DIM}Ikuti langkah di bawah untuk mendapatkan cookie baru:${NC}"
    blank
    echo -e "  1. Buka ${CYAN}https://moltarena.crosstoken.io${NC} → pastikan LOGIN"
    echo -e "  2. Tekan ${BOLD}F12${NC} → tab ${BOLD}Application${NC} → Cookies → crosstoken.io"
    echo -e "  3. Klik baris pertama → ${BOLD}Ctrl+A${NC} (pilih semua) → ${BOLD}Ctrl+C${NC} (copy)"
    echo -e "  4. Paste di bawah ini lalu ${BOLD}Ctrl+D${NC} untuk selesai:"
    blank
    line

    RAW_COOKIE=""
    while IFS= read -r cookie_line; do
        RAW_COOKIE="${RAW_COOKIE}${cookie_line}
"
    done

    line
    blank

    if [ -z "$(echo "$RAW_COOKIE" | tr -d '[:space:]')" ]; then
        warn "Cookie kosong — tidak ada perubahan"
        return
    fi

    PARSED=$(parse_cookie "$RAW_COOKIE" 2>/tmp/cookie_parse_err || true)
    if [ -z "$PARSED" ]; then
        warn "Gagal parse: $(cat /tmp/cookie_parse_err 2>/dev/null)"
        return
    fi

    # Update MOLT_SESSION_COOKIE di .env
    if grep -q "^MOLT_SESSION_COOKIE=" "$ENV_FILE"; then
        # Pakai Python untuk replace karena cookie sangat panjang
        $PYTHON_BIN - <<PYEOF
import re
from pathlib import Path
env = Path("${ENV_FILE}")
text = env.read_text()
text = re.sub(r'^MOLT_SESSION_COOKIE=.*$',
              f'MOLT_SESSION_COOKIE=${PARSED}',
              text, flags=re.MULTILINE)
env.write_text(text)
print("ok")
PYEOF
    else
        echo "MOLT_SESSION_COOKIE=${PARSED}" >> "$ENV_FILE"
    fi

    if echo "$PARSED" | grep -q "sb-hkxnuxudaopdpmlcfqjf-auth-token"; then
        success "Cookie diperbarui! Token Supabase ditemukan ✓"
    else
        warn "Cookie disimpan tapi token sb-auth-token tidak ditemukan"
    fi
}

# ══════════════════════════════════════════════════════════════
choose_run_mode() {
    blank
    echo -e "  ${BOLD}🚀 Cara menjalankan bot:${NC}"
    blank
    echo -e "  ${CYAN}[1]${NC} Test 1 battle    ${DIM}— verifikasi API Key & koneksi${NC}"
    echo -e "  ${CYAN}[2]${NC} Foreground        ${DIM}— Ctrl+C untuk stop + lihat summary${NC}"
    echo -e "  ${CYAN}[3]${NC} Screen (bg)       ${DIM}— tetap jalan walau SSH disconnect${NC}"
    echo -e "  ${CYAN}[4]${NC} Systemd service   ${DIM}— auto-start saat server reboot${NC}"
    echo -e "  ${CYAN}[5]${NC} Keluar"
    blank
    echo -ne "  ${BOLD}Pilih [1-5]: ${NC}"
    read -r MODE
    case "$MODE" in
        1) run_test ;;
        2) run_foreground ;;
        3) run_screen ;;
        4) run_systemd ;;
        5) exit 0 ;;
        *) run_foreground ;;
    esac
}

run_test() {
    blank; success "Test 1 battle (debug mode)..."
    blank
    source "$VENV_DIR/bin/activate"
    "$PYTHON_BIN" "$MAIN_SCRIPT" --once --debug
    blank
    echo -ne "  ${BOLD}Lanjut loop penuh? [y/N]: ${NC}"
    read -r C
    [[ "$C" =~ ^[Yy]$ ]] && run_foreground || exit 0
}

run_foreground() {
    blank; success "Menjalankan... (Ctrl+C untuk stop + summary)"
    blank
    source "$VENV_DIR/bin/activate"
    exec "$PYTHON_BIN" "$MAIN_SCRIPT"
}

run_screen() {
    step "Background dengan screen..."
    command -v screen &>/dev/null || sudo apt install screen -y
    SESSION="molt-bot"
    screen -S "$SESSION" -X quit 2>/dev/null || true
    sleep 1
    screen -dmS "$SESSION" bash -c "
        source '$VENV_DIR/bin/activate'
        '$PYTHON_BIN' '$MAIN_SCRIPT'
    "
    sleep 2
    if screen -list | grep -q "$SESSION"; then
        success "Bot berjalan di background!"
    else
        warn "Screen gagal, coba foreground"; return
    fi
    blank; line
    echo -e "  ${CYAN}screen -r $SESSION${NC}              → Lihat log live"
    echo -e "  ${CYAN}Ctrl+A → D${NC}                      → Detach"
    echo -e "  ${CYAN}screen -S $SESSION -X quit${NC}       → Stop bot"
    echo -e "  ${CYAN}tail -f $LOG_FILE${NC}                → Log file"
    line
}

run_systemd() {
    step "Install sebagai systemd service..."
    CURRENT_USER=$(whoami)
    cat > /tmp/molt-battle.service <<SVCEOF
[Unit]
Description=MoltArena Auto Battle Bot v10
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python ${MAIN_SCRIPT}
Restart=always
RestartSec=60
EnvironmentFile=${ENV_FILE}

[Install]
WantedBy=multi-user.target
SVCEOF
    sudo cp /tmp/molt-battle.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable molt-battle
    sudo systemctl restart molt-battle
    sleep 2
    STATUS=$(sudo systemctl is-active molt-battle 2>/dev/null || echo "unknown")
    [ "$STATUS" = "active" ] && success "Service aktif!" || warn "Status: $STATUS"
    blank; line
    echo -e "  ${CYAN}sudo systemctl status molt-battle${NC}"
    echo -e "  ${CYAN}sudo journalctl -u molt-battle -f${NC}"
    echo -e "  ${CYAN}sudo systemctl restart molt-battle${NC}"
    echo -e "  ${CYAN}sudo systemctl stop molt-battle${NC}"
    line
}

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
print_banner
check_python
[ ! -f "$MAIN_SCRIPT" ] && { error "molt_auto_battle.py tidak ditemukan!"; exit 1; }
setup_venv
install_deps

step "Cek .env..."
if [ ! -f "$ENV_FILE" ]; then
    warn ".env tidak ditemukan → Setup konfigurasi baru..."
    blank
    run_full_setup
else
    success ".env ditemukan"
    show_config
    menu_env_ada
fi

show_config
choose_run_mode
