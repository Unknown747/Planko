#!/usr/bin/env bash
# setup.sh - Setup environment untuk Auto Bet Plinko Stake.com
# Gunakan di VPS (Ubuntu/Debian/CentOS) atau Replit
# Jalankan: bash setup.sh

set -e

# ============================================================
# Helper
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
die()     { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo "======================================================"
echo "   Plinko Auto-Bet -- Setup Script"
echo "======================================================"
echo ""

# ============================================================
# 1. Cek Python 3
# ============================================================
info "Memeriksa Python 3..."
if ! command -v python3 >/dev/null 2>&1; then
    warn "Python 3 tidak ditemukan. Mencoba install..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y python3 python3-pip python3-venv
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y python3 python3-pip
    else
        die "Tidak bisa install Python otomatis. Install manual dulu."
    fi
fi
PYTHON_VERSION=$(python3 --version 2>&1)
success "Ditemukan: $PYTHON_VERSION"

# ============================================================
# 2. Virtual environment
# ============================================================
info "Menyiapkan virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    success "Virtual environment dibuat di ./venv"
else
    success "Virtual environment sudah ada."
fi

# shellcheck disable=SC1091
source venv/bin/activate

# ============================================================
# 3. Install dependensi
# ============================================================
info "Menginstall dependensi Python..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
success "Dependensi terinstall."

# ============================================================
# 4. Baca nilai lama dari .env jika ada
# ============================================================
ENV_FILE=".env"
OLD_TOKEN="" OLD_RISK="" OLD_ROWS="" OLD_BET="" OLD_CURRENCY=""
OLD_DELAY="" OLD_STOP_LOSS="" OLD_TAKE_PROFIT="" OLD_TP_DELAY="" OLD_WAGER_TARGET="" OLD_MAX_ERRORS="" OLD_MAX_RETRIES=""
OLD_STRATEGY="" OLD_BET_MULT="" OLD_WIN_CAP="" OLD_MAX_BET=""

if [ -f "$ENV_FILE" ]; then
    OLD_TOKEN=$(grep -E '^STAKE_API_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_RISK=$(grep -E '^RISK=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_ROWS=$(grep -E '^ROWS=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_BET=$(grep -E '^BET_AMOUNT=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_CURRENCY=$(grep -E '^CURRENCY=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_DELAY=$(grep -E '^BASE_DELAY_MS=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_STOP_LOSS=$(grep -E '^STOP_LOSS=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_STRATEGY=$(grep -E '^STRATEGY=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_BET_MULT=$(grep -E '^BET_MULTIPLIER=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_WIN_CAP=$(grep -E '^WIN_STREAK_CAP=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_MAX_BET=$(grep -E '^MAX_BET=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_TAKE_PROFIT=$(grep -E '^TAKE_PROFIT=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_TP_DELAY=$(grep -E '^TAKE_PROFIT_DELAY_SEC=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_WAGER_TARGET=$(grep -E '^WAGER_TARGET=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_MAX_ERRORS=$(grep -E '^MAX_CONSECUTIVE_ERRORS=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    OLD_MAX_RETRIES=$(grep -E '^MAX_RATE_LIMIT_RETRIES=' "$ENV_FILE" | cut -d= -f2- | tr -d "\"'" || true)
    warn "File .env sudah ada. Tekan Enter untuk mempertahankan nilai lama."
else
    info "File .env belum ada, akan dibuat."
fi

# ============================================================
# 5. Fungsi validasi
# ============================================================

# prompt <teks> <default>
prompt_val() {
    local TEXT="$1" DEFAULT="$2" RESULT
    if [ -n "$DEFAULT" ]; then
        read -rp "  $TEXT [default: $DEFAULT]: " RESULT
        RESULT="${RESULT:-$DEFAULT}"
    else
        read -rp "  $TEXT: " RESULT
    fi
    printf '%s' "$RESULT"
}

# is_integer <nilai>  -- return 0 jika ya
is_integer() { echo "$1" | grep -qE '^[0-9]+$'; }

# is_number <nilai>   -- return 0 jika integer atau float positif
is_number()  { echo "$1" | grep -qE '^[0-9]+([.][0-9]+)?$'; }

# is_nonzero <nilai>  -- return 0 jika tidak 0
is_nonzero() { ! echo "$1" | grep -qE '^0+(\.0+)?$'; }

# ============================================================
# 6. Input interaktif + validasi
# ============================================================
echo ""
echo "------------------------------------------------------"
echo "  Masukkan konfigurasi (Enter = pakai nilai default)"
echo "------------------------------------------------------"
echo ""

# --- Token (wajib) ---
echo "  Cara dapat token:"
echo "  Buka Stake.com > login > F12 > tab Network"
echo "  > klik request ke _api/graphql > Request Headers > salin x-access-token"
echo ""
while true; do
    STAKE_API_TOKEN=$(prompt_val "STAKE_API_TOKEN" "$OLD_TOKEN")
    if [ -n "$STAKE_API_TOKEN" ]; then break; fi
    warn "STAKE_API_TOKEN tidak boleh kosong."
done

echo ""
echo "--- Pengaturan Game ---"

while true; do
    RISK=$(prompt_val "RISK (LOW / MEDIUM / HIGH)" "${OLD_RISK:-LOW}")
    RISK=$(echo "$RISK" | tr '[:lower:]' '[:upper:]')
    case "$RISK" in
        LOW|MEDIUM|HIGH) break ;;
        *) warn "RISK harus LOW, MEDIUM, atau HIGH." ;;
    esac
done

while true; do
    ROWS=$(prompt_val "ROWS jumlah baris (8-16)" "${OLD_ROWS:-8}")
    if is_integer "$ROWS" && [ "$ROWS" -ge 8 ] && [ "$ROWS" -le 16 ]; then break; fi
    warn "ROWS harus bilangan bulat antara 8 dan 16."
done

while true; do
    BET_AMOUNT=$(prompt_val "BET_AMOUNT nominal bet per round (> 0)" "${OLD_BET:-500}")
    if is_number "$BET_AMOUNT" && is_nonzero "$BET_AMOUNT"; then break; fi
    warn "BET_AMOUNT harus angka positif lebih dari 0 (contoh: 500 atau 0.0005)."
done

CURRENCY=$(prompt_val "CURRENCY (IDR / BTC / ETH / USDT / dll)" "${OLD_CURRENCY:-IDR}")
CURRENCY=$(echo "$CURRENCY" | tr '[:lower:]' '[:upper:]')

echo ""
echo "--- Strategi Betting ---"
echo "  FLAT          = bet selalu tetap (aman, default)"
echo "  ANTI_MARTINGALE = naik saat menang, reset saat kalah (aman untuk modal kecil)"
echo ""

while true; do
    STRATEGY=$(prompt_val "STRATEGY (FLAT / ANTI_MARTINGALE)" "${OLD_STRATEGY:-ANTI_MARTINGALE}")
    STRATEGY=$(echo "$STRATEGY" | tr '[:lower:]' '[:upper:]')
    if [[ "$STRATEGY" == "FLAT" || "$STRATEGY" == "ANTI_MARTINGALE" ]]; then break; fi
    warn "STRATEGY harus FLAT atau ANTI_MARTINGALE."
done

if [ "$STRATEGY" = "ANTI_MARTINGALE" ]; then
    while true; do
        BET_MULTIPLIER=$(prompt_val "BET_MULTIPLIER pengali bet saat menang (> 1, contoh: 2)" "${OLD_BET_MULT:-2}")
        if is_number "$BET_MULTIPLIER" && is_nonzero "$BET_MULTIPLIER"; then
            # cek > 1 dengan python3 karena bash tidak handle float
            if python3 -c "import sys; sys.exit(0 if float('${BET_MULTIPLIER}') > 1 else 1)" 2>/dev/null; then
                break
            fi
        fi
        warn "BET_MULTIPLIER harus angka lebih dari 1 (contoh: 2 atau 1.5)."
    done

    while true; do
        WIN_STREAK_CAP=$(prompt_val "WIN_STREAK_CAP maks lipat berturut-turut sebelum reset (min 1)" "${OLD_WIN_CAP:-3}")
        if is_integer "$WIN_STREAK_CAP" && [ "$WIN_STREAK_CAP" -ge 1 ]; then break; fi
        warn "WIN_STREAK_CAP harus bilangan bulat >= 1."
    done

    while true; do
        MAX_BET=$(prompt_val "MAX_BET batas atas nominal bet (0 = tidak dibatas)" "${OLD_MAX_BET:-0}")
        if is_number "$MAX_BET"; then break; fi
        warn "MAX_BET harus angka >= 0."
    done
else
    BET_MULTIPLIER="${OLD_BET_MULT:-2}"
    WIN_STREAK_CAP="${OLD_WIN_CAP:-3}"
    MAX_BET="${OLD_MAX_BET:-0}"
fi

echo ""
echo "--- Kontrol Bot ---"

while true; do
    BASE_DELAY_MS=$(prompt_val "BASE_DELAY_MS jeda antar bet dalam ms (min 100)" "${OLD_DELAY:-200}")
    if is_integer "$BASE_DELAY_MS" && [ "$BASE_DELAY_MS" -ge 100 ]; then break; fi
    warn "BASE_DELAY_MS harus bilangan bulat >= 100."
done

while true; do
    STOP_LOSS=$(prompt_val "STOP_LOSS berhenti jika saldo <= nilai ini (0 = nonaktif)" "${OLD_STOP_LOSS:-10000}")
    if is_number "$STOP_LOSS"; then break; fi
    warn "STOP_LOSS harus angka >= 0."
done

while true; do
    TAKE_PROFIT=$(prompt_val "TAKE_PROFIT berhenti jika profit bersih >= nilai ini (0 = nonaktif)" "${OLD_TAKE_PROFIT:-10000}")
    if is_number "$TAKE_PROFIT"; then break; fi
    warn "TAKE_PROFIT harus angka >= 0."
done

while true; do
    TAKE_PROFIT_DELAY_SEC=$(prompt_val "TAKE_PROFIT_DELAY_SEC countdown sebelum stop saat take profit (detik)" "${OLD_TP_DELAY:-30}")
    if is_integer "$TAKE_PROFIT_DELAY_SEC" && [ "$TAKE_PROFIT_DELAY_SEC" -ge 0 ]; then break; fi
    warn "TAKE_PROFIT_DELAY_SEC harus bilangan bulat >= 0."
done

while true; do
    WAGER_TARGET=$(prompt_val "WAGER_TARGET batas total wager (0 = unlimited)" "${OLD_WAGER_TARGET:-0}")
    if is_number "$WAGER_TARGET"; then break; fi
    warn "WAGER_TARGET harus angka >= 0."
done

while true; do
    MAX_CONSECUTIVE_ERRORS=$(prompt_val "MAX_CONSECUTIVE_ERRORS maks error berturut-turut (min 1)" "${OLD_MAX_ERRORS:-5}")
    if is_integer "$MAX_CONSECUTIVE_ERRORS" && [ "$MAX_CONSECUTIVE_ERRORS" -ge 1 ]; then break; fi
    warn "MAX_CONSECUTIVE_ERRORS harus bilangan bulat >= 1."
done

while true; do
    MAX_RATE_LIMIT_RETRIES=$(prompt_val "MAX_RATE_LIMIT_RETRIES retry saat rate-limit 429 (min 1)" "${OLD_MAX_RETRIES:-10}")
    if is_integer "$MAX_RATE_LIMIT_RETRIES" && [ "$MAX_RATE_LIMIT_RETRIES" -ge 1 ]; then break; fi
    warn "MAX_RATE_LIMIT_RETRIES harus bilangan bulat >= 1."
done

# ============================================================
# 7. Tulis .env
# ============================================================
{
    echo "# Auto-generated by setup.sh -- $(date)"
    echo "# Edit manual atau jalankan ulang: bash setup.sh"
    echo ""
    echo "STAKE_API_TOKEN=${STAKE_API_TOKEN}"
    echo ""
    echo "RISK=${RISK}"
    echo "ROWS=${ROWS}"
    echo "BET_AMOUNT=${BET_AMOUNT}"
    echo "CURRENCY=${CURRENCY}"
    echo ""
    echo "STRATEGY=${STRATEGY}"
    echo "BET_MULTIPLIER=${BET_MULTIPLIER}"
    echo "WIN_STREAK_CAP=${WIN_STREAK_CAP}"
    echo "MAX_BET=${MAX_BET}"
    echo ""
    echo "BASE_DELAY_MS=${BASE_DELAY_MS}"
    echo "STOP_LOSS=${STOP_LOSS}"
    echo "TAKE_PROFIT=${TAKE_PROFIT}"
    echo "TAKE_PROFIT_DELAY_SEC=${TAKE_PROFIT_DELAY_SEC}"
    echo "WAGER_TARGET=${WAGER_TARGET}"
    echo "MAX_CONSECUTIVE_ERRORS=${MAX_CONSECUTIVE_ERRORS}"
    echo "MAX_RATE_LIMIT_RETRIES=${MAX_RATE_LIMIT_RETRIES}"
} > "$ENV_FILE"

success "File .env berhasil ditulis."

# Pastikan .env tidak masuk git
if [ -f ".gitignore" ]; then
    if ! grep -qxF '.env' .gitignore; then
        echo '.env' >> .gitignore
        success ".env ditambahkan ke .gitignore."
    fi
else
    echo '.env' > .gitignore
    success ".gitignore dibuat."
fi

# ============================================================
# 8. Selesai
# ============================================================
echo ""
echo "======================================================"
success "Setup selesai!"
echo ""
echo "  Untuk menjalankan bot:"
echo ""
echo "    source venv/bin/activate"
echo "    python3 main.py"
echo ""
echo "  Untuk jalan di background (VPS):"
echo ""
echo "    source venv/bin/activate"
echo "    nohup python3 main.py > plinko.log 2>&1 &"
echo "    echo \"PID: \$!\""
echo ""
echo "  Lihat log:"
echo "    tail -f plinko.log"
echo ""
echo "  Stop bot background:"
echo "    kill \$(pgrep -f 'python3 main.py')"
echo ""
echo "======================================================"
