#!/usr/bin/env python3
# main.py - Auto Bet Plinko Stake.com
import requests
import random   # untuk bet acak & delay acak
import signal
import time
import os
import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

# ==================== PEMILIHAN MODE / CONFIG ====================
#
# Cara pakai:
#   python3 main.py               → tampilkan menu pilihan mode
#   python3 main.py profit        → mode profit (muncul sub-menu pin)
#   python3 main.py profit --rows 14 → mode profit 14 pin langsung
#   python3 main.py wager         → langsung mode wager
#   python3 main.py --config file.env → file config kustom apapun
#
# Urutan prioritas (dari tertinggi ke terendah):
#   1. Env var yang sudah ada di shell (export VAR=...)
#   2. File .env (token & override personal)
#   3. File preset mode / --config (pengaturan game default)
#
# Artinya: cukup simpan STAKE_API_TOKEN di .env saja, lalu pilih mode
# lewat argumen — tidak perlu copy-paste file config.

_parser = argparse.ArgumentParser(
    prog='main.py',
    description='Auto Bet Plinko Stake.com',
    add_help=False,   # kita handle sendiri agar --help tetap bisa
)
_parser.add_argument('mode', nargs='?', choices=['profit', 'wager'])
_parser.add_argument('--config', '-c', metavar='FILE')
_parser.add_argument('--rows', type=int, choices=[14, 16],
                     help='Jumlah pin untuk mode profit (14 atau 16); lewati menu pin jika diisi')
_parser.add_argument('--help', '-h', action='store_true')
_args = _parser.parse_args()

if _args.help:
    print("Cara pakai:")
    print("  python3 main.py               → tampilkan menu pilihan mode")
    print("  python3 main.py profit        → mode profit (muncul menu pin)")
    print("  python3 main.py profit --rows 14  → mode profit 14 pin langsung")
    print("  python3 main.py profit --rows 16  → mode profit 16 pin langsung")
    print("  python3 main.py wager         → langsung mode wager")
    print("  python3 main.py --config file.env → file config kustom")
    sys.exit(0)

def _tampilkan_menu():
    """Tampilkan menu utama: pilih mode profit atau wager."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║     🎰  PLINKO AUTO-BET STAKE.COM    ║")
    print("  ╠══════════════════════════════════════╣")
    print("  ║                                      ║")
    print("  ║   Pilih mode yang ingin dijalankan:  ║")
    print("  ║                                      ║")
    print("  ║   1.  💰 PROFIT                      ║")
    print("  ║       Bet Rp 50–100 acak, cari cuan  ║")
    print("  ║       Expert mode, 1 bola per gilir  ║")
    print("  ║                                      ║")
    print("  ║   2.  🎯 WAGER                       ║")
    print("  ║       Bet Rp 500, max 2x recovery    ║")
    print("  ║       Farming bonus, se-safe mungkin ║")
    print("  ║                                      ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    while True:
        try:
            pilihan = input("  Masukkan pilihan [1/2] : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n⏹️  Dibatalkan.")
            sys.exit(0)
        if pilihan == '1':
            return 'profit'
        elif pilihan == '2':
            return 'wager'
        else:
            print("  ⚠️  Masukkan 1 atau 2.")

def _tampilkan_menu_pins():
    """Sub-menu pilihan jumlah pin untuk mode Profit."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║      📌  PILIH JUMLAH PIN            ║")
    print("  ╠══════════════════════════════════════╣")
    print("  ║                                      ║")
    print("  ║   1.  🎯 14 PIN                      ║")
    print("  ║       Multiplier max ~420x            ║")
    print("  ║       Lebih sering kena tengah        ║")
    print("  ║                                      ║")
    print("  ║   2.  🚀 16 PIN                      ║")
    print("  ║       Multiplier max ~1000x           ║")
    print("  ║       Lebih ekstrem, potensi jackpot  ║")
    print("  ║                                      ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    while True:
        try:
            pilihan = input("  Masukkan pilihan [1/2] : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n⏹️  Dibatalkan.")
            sys.exit(0)
        if pilihan == '1':
            return 14
        elif pilihan == '2':
            return 16
        else:
            print("  ⚠️  Masukkan 1 atau 2.")

# Tentukan mode: dari argumen atau tanya user
_config_file = None
_mode = None
_rows_override = None

if _args.config:
    # File config kustom langsung — lewati semua menu
    _config_file = _args.config
    if not os.path.exists(_config_file):
        print(f"❌ File config tidak ditemukan: {_config_file}")
        sys.exit(1)
else:
    # Mode dari argumen CLI atau menu interaktif
    _mode = _args.mode if _args.mode else _tampilkan_menu()
    _config_file = f'config_{_mode}.env'
    if not os.path.exists(_config_file):
        print(f"❌ File preset tidak ditemukan: {_config_file}")
        sys.exit(1)

    # Mode profit: tanya jumlah pin (14 atau 16)
    # --rows di CLI melewati menu pin (berguna untuk nohup/VPS non-interaktif)
    if _mode == 'profit':
        if _args.rows:
            _rows_override = _args.rows
        else:
            _rows_override = _tampilkan_menu_pins()

# Muat config dengan urutan prioritas yang benar:
#   shell / Replit Secrets  (tertinggi — sudah ada di os.environ sebelum script jalan)
#   .env                    (tengah   — token & override personal)
#   preset config           (terendah — nilai default game)
#
# Teknik: simpan env shell/Secrets sebelum load_dotenv, lalu pulihkan sesudahnya.
# Ini perlu karena load_dotenv(override=True) akan menimpa shell vars jika tidak dijaga.
_shell_env = dict(os.environ)                   # simpan env shell / Replit Secrets
load_dotenv(dotenv_path=_config_file, override=True)  # preset: set semua nilai dasar
load_dotenv(override=True)                      # .env menimpa preset
os.environ.update(_shell_env)                   # shell/Secrets kembali jadi yang utama

# Terapkan override pin setelah load_dotenv agar mengalahkan nilai preset
if _rows_override is not None:
    os.environ['ROWS'] = str(_rows_override)

_mode_label = _config_file.replace('config_', '').replace('.env', '').upper()
_pin_label   = f" ({_rows_override} PIN)" if _rows_override else ""
print(f"  📂 Mode   : {_mode_label}{_pin_label}")

# ==================== KONFIGURASI ====================

VALID_RISKS = {'LOW', 'MEDIUM', 'HIGH'}
VALID_ROWS = set(range(8, 17))  # 8–16

def _parse_env():
    """Parse dan validasi semua env var. Raise ValueError dengan pesan jelas jika ada yang salah."""
    errors = []

    def get_float(key, default):
        val = os.getenv(key, str(default))
        try:
            return float(val)
        except ValueError:
            errors.append(f"{key}='{val}' bukan angka desimal yang valid.")
            return default

    def get_int(key, default):
        val = os.getenv(key, str(default))
        try:
            return int(val)
        except ValueError:
            errors.append(f"{key}='{val}' bukan bilangan bulat yang valid.")
            return default

    risk = os.getenv('RISK', 'LOW').upper()
    if risk not in VALID_RISKS:
        errors.append(f"RISK='{risk}' tidak valid. Pilihan: LOW, MEDIUM, HIGH.")
    risk_enum = risk.lower()  # Stake API pakai lowercase enum: low/medium/high

    rows = get_int('ROWS', 8)
    if rows not in VALID_ROWS:
        errors.append(f"ROWS={rows} tidak valid. Pilihan: 8 hingga 16.")

    bet_amount = get_float('BET_AMOUNT', 500)
    if bet_amount <= 0:
        errors.append(f"BET_AMOUNT={bet_amount} harus lebih dari 0.")

    # Bet acak: jika BET_AMOUNT_MIN & BET_AMOUNT_MAX diisi, base bet dirandom tiap reset
    # Jika tidak diisi (0), pakai BET_AMOUNT tetap seperti biasa
    bet_amount_min = get_float('BET_AMOUNT_MIN', 0)
    bet_amount_max = get_float('BET_AMOUNT_MAX', 0)
    if bet_amount_min > 0 or bet_amount_max > 0:
        if bet_amount_min <= 0:
            errors.append("BET_AMOUNT_MIN harus > 0 jika BET_AMOUNT_MAX diisi.")
        if bet_amount_max <= 0:
            errors.append("BET_AMOUNT_MAX harus > 0 jika BET_AMOUNT_MIN diisi.")
        if bet_amount_min > 0 and bet_amount_max > 0 and bet_amount_min >= bet_amount_max:
            errors.append(f"BET_AMOUNT_MIN ({bet_amount_min}) harus lebih kecil dari BET_AMOUNT_MAX ({bet_amount_max}).")

    # Delay acak: jika BASE_DELAY_MIN_MS & BASE_DELAY_MAX_MS diisi, delay dirandom per bet
    # Jika tidak diisi (0), pakai BASE_DELAY_MS tetap
    base_delay = get_int('BASE_DELAY_MS', 200)
    if base_delay < 0:
        errors.append(f"BASE_DELAY_MS={base_delay} tidak boleh negatif.")
    delay_min = get_int('BASE_DELAY_MIN_MS', 0)
    delay_max = get_int('BASE_DELAY_MAX_MS', 0)
    if delay_min > 0 or delay_max > 0:
        if delay_min <= 0:
            errors.append("BASE_DELAY_MIN_MS harus > 0 jika BASE_DELAY_MAX_MS diisi.")
        if delay_max <= 0:
            errors.append("BASE_DELAY_MAX_MS harus > 0 jika BASE_DELAY_MIN_MS diisi.")
        if delay_min > 0 and delay_max > 0 and delay_min >= delay_max:
            errors.append(f"BASE_DELAY_MIN_MS ({delay_min}) harus lebih kecil dari BASE_DELAY_MAX_MS ({delay_max}).")

    stop_loss = get_float('STOP_LOSS', 10000)
    if stop_loss < 0:
        errors.append(f"STOP_LOSS={stop_loss} tidak boleh negatif.")

    # Stop loss relatif: berhenti jika rugi >= MAX_LOSS dari modal awal sesi
    # Berbeda dari STOP_LOSS (saldo absolut) — ini berbasis selisih dari awal
    max_loss = get_float('MAX_LOSS', 0)
    if max_loss < 0:
        errors.append(f"MAX_LOSS={max_loss} tidak boleh negatif.")

    # Jackpot stop: berhenti LANGSUNG (tanpa countdown) jika multiplier >= nilai ini
    # Contoh: JACKPOT_STOP_MULTIPLIER=420 → kunci profit saat kena x420 atau lebih
    jackpot_stop = get_float('JACKPOT_STOP_MULTIPLIER', 0)   # 0 = nonaktif
    if jackpot_stop < 0:
        errors.append(f"JACKPOT_STOP_MULTIPLIER={jackpot_stop} tidak boleh negatif.")

    take_profit = get_float('TAKE_PROFIT', 0)
    if take_profit < 0:
        errors.append(f"TAKE_PROFIT={take_profit} tidak boleh negatif.")

    take_profit_delay = get_int('TAKE_PROFIT_DELAY_SEC', 30)
    if take_profit_delay < 0:
        errors.append(f"TAKE_PROFIT_DELAY_SEC={take_profit_delay} tidak boleh negatif.")

    # --- Strategi betting ---
    valid_strategies = {'FLAT', 'ANTI_MARTINGALE', 'MARTINGALE'}
    strategy = os.getenv('STRATEGY', 'FLAT').upper()
    if strategy not in valid_strategies:
        errors.append(f"STRATEGY='{strategy}' tidak valid. Pilihan: FLAT, ANTI_MARTINGALE, MARTINGALE.")

    bet_multiplier = get_float('BET_MULTIPLIER', 2.0)
    win_streak_cap = get_int('WIN_STREAK_CAP', 3)
    loss_streak_cap = get_int('LOSS_STREAK_CAP', 0)  # 0 = tidak ada batas (pure Martingale)
    max_bet = get_float('MAX_BET', 0)  # 0 = tidak ada batas

    # Validasi parameter Anti-Martingale hanya jika strategi benar-benar memakainya
    if strategy == 'ANTI_MARTINGALE':
        if bet_multiplier <= 1.0:
            errors.append(f"BET_MULTIPLIER={bet_multiplier} harus lebih dari 1 (contoh: 2).")
        if win_streak_cap < 1:
            errors.append(f"WIN_STREAK_CAP={win_streak_cap} harus minimal 1.")
        if max_bet < 0:
            errors.append(f"MAX_BET={max_bet} tidak boleh negatif.")

    # Validasi parameter Martingale
    if strategy == 'MARTINGALE':
        if bet_multiplier <= 1.0:
            errors.append(f"BET_MULTIPLIER={bet_multiplier} harus lebih dari 1 (contoh: 2).")
        if max_bet < 0:
            errors.append(f"MAX_BET={max_bet} tidak boleh negatif.")
        if loss_streak_cap < 0:
            errors.append(f"LOSS_STREAK_CAP={loss_streak_cap} tidak boleh negatif.")

    max_errors = get_int('MAX_CONSECUTIVE_ERRORS', 5)
    if max_errors < 1:
        errors.append(f"MAX_CONSECUTIVE_ERRORS={max_errors} harus minimal 1.")

    max_retries = get_int('MAX_RATE_LIMIT_RETRIES', 10)
    if max_retries < 1:
        errors.append(f"MAX_RATE_LIMIT_RETRIES={max_retries} harus minimal 1.")

    currency_raw = os.getenv('CURRENCY', 'IDR')
    currency_enum = currency_raw.lower()  # Stake API pakai lowercase enum: idr/btc/eth

    # Log file — 'auto' = generate nama otomatis, 'NONE' = nonaktif
    log_file_raw = os.getenv('LOG_FILE', 'auto').strip()
    if log_file_raw.upper() == 'NONE':
        log_file = ''
    elif log_file_raw.lower() == 'auto':
        log_file = datetime.now().strftime('plinko_%Y%m%d_%H%M%S.csv')
    else:
        log_file = log_file_raw

    log_max_lines = get_int('LOG_MAX_LINES', 1000)
    if log_max_lines < 10:
        errors.append(f"LOG_MAX_LINES={log_max_lines} harus minimal 10.")

    # Auto-reset sesi & ringkasan berkala
    session_reset_bets = get_int('SESSION_RESET_BETS', 0)
    if session_reset_bets < 0:
        errors.append(f"SESSION_RESET_BETS={session_reset_bets} tidak boleh negatif.")

    session_reset_mins = get_int('SESSION_RESET_MINUTES', 0)
    if session_reset_mins < 0:
        errors.append(f"SESSION_RESET_MINUTES={session_reset_mins} tidak boleh negatif.")

    summary_every = get_int('SUMMARY_EVERY_BETS', 0)
    if summary_every != 0 and summary_every < 5:
        errors.append(f"SUMMARY_EVERY_BETS={summary_every} harus minimal 5 atau 0 (nonaktif).")

    if errors:
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        raise ValueError(f"\nKesalahan konfigurasi .env:\n{msg}\n\nPerbaiki file .env lalu jalankan ulang.")

    return {
        'STAKE_API_TOKEN': os.getenv('STAKE_API_TOKEN', ''),
        'RISK': risk,
        'RISK_ENUM': risk_enum,               # 'low'/'medium'/'high' untuk GraphQL
        'ROWS': rows,
        'BET_AMOUNT': bet_amount,             # bet dasar tetap (dipakai jika MIN/MAX tidak diisi)
        'BET_AMOUNT_MIN': bet_amount_min,     # batas bawah bet acak (0 = nonaktif)
        'BET_AMOUNT_MAX': bet_amount_max,     # batas atas bet acak (0 = nonaktif)
        'CURRENCY': currency_raw.upper(),
        'CURRENCY_ENUM': currency_enum,
        'BASE_DELAY_MS': base_delay,          # delay tetap (dipakai jika MIN/MAX tidak diisi)
        'BASE_DELAY_MIN_MS': delay_min,       # batas bawah delay acak (0 = nonaktif)
        'BASE_DELAY_MAX_MS': delay_max,       # batas atas delay acak
        'STOP_LOSS': stop_loss,               # saldo absolut minimum sebelum berhenti
        'MAX_LOSS': max_loss,                 # rugi relatif maks dari modal awal sesi (0 = nonaktif)
        'JACKPOT_STOP_MULTIPLIER': jackpot_stop,  # multiplier ambang jackpot-stop (0 = nonaktif)
        'TAKE_PROFIT': take_profit,
        'TAKE_PROFIT_DELAY_SEC': take_profit_delay,
        'STRATEGY': strategy,
        'BET_MULTIPLIER': bet_multiplier,
        'WIN_STREAK_CAP': win_streak_cap,
        'LOSS_STREAK_CAP': loss_streak_cap,
        'MAX_BET': max_bet,
        'MAX_CONSECUTIVE_ERRORS': max_errors,
        'MAX_RATE_LIMIT_RETRIES': max_retries,
        'GRAPHQL_URL': os.getenv('GRAPHQL_URL', 'https://stake.com/_api/graphql'),
        'LOG_FILE': log_file,
        'LOG_MAX_LINES': log_max_lines,
        'SESSION_RESET_BETS': session_reset_bets,
        'SESSION_RESET_MINUTES': session_reset_mins,
        'SUMMARY_EVERY_BETS': summary_every,
    }

try:
    CONFIG = _parse_env()
except ValueError as _cfg_err:
    print(_cfg_err)
    sys.exit(1)

# ==================== HELPER BET ACAK ====================

def get_base_bet() -> float:
    """
    Kembalikan nominal bet dasar untuk satu siklus.

    Jika BET_AMOUNT_MIN dan BET_AMOUNT_MAX diisi → pilih secara acak di antara keduanya.
    Ini membuat pola bet lebih tidak terduga (anti-deteksi pola oleh server).
    Jika tidak diisi → pakai BET_AMOUNT tetap seperti biasa.
    """
    if CONFIG['BET_AMOUNT_MIN'] > 0 and CONFIG['BET_AMOUNT_MAX'] > 0:
        # random.uniform → float acak termasuk batas bawah dan atas
        raw = random.uniform(CONFIG['BET_AMOUNT_MIN'], CONFIG['BET_AMOUNT_MAX'])
        # Bulatkan ke kelipatan 50 terdekat agar nominal rapi (50, 100, 150, dst.)
        step = 50
        return max(CONFIG['BET_AMOUNT_MIN'], round(raw / step) * step)
    return CONFIG['BET_AMOUNT']

# ==================== STATE ====================
class State:
    def __init__(self):
        self.balance = 0.0
        self.initial_balance = 0.0          # TIDAK pernah diubah setelah startup
        self.balance_initialized = False    # True setelah saldo awal berhasil diambil
        self.total_wagered = 0.0
        self.total_bets = 0
        self.is_running = True
        self.consecutive_errors = 0
        self.start_time = datetime.now()
        # Strategi
        self.current_bet = get_base_bet()   # bet pertama: acak jika MIN/MAX diisi
        self.win_streak = 0                       # berapa kali menang berturut-turut
        self.loss_streak = 0                      # berapa kali kalah berturut-turut (Martingale)
        self.martingale_capped = False            # True jika bet terakhir sudah kena MAX_BET cap
        self.win_count = 0                        # total bet yang menang (untuk win rate final)
        # Take-profit rearm
        # Saat take-profit countdown dibatalkan, threshold naik agar tidak langsung trigger lagi.
        # Menyimpan "floor" net_profit — trigger berikutnya hanya ketika:
        #   net_profit >= tp_rearm_floor + TAKE_PROFIT
        # initial_balance TIDAK disentuh sehingga net_profit selalu akurat sepanjang sesi.
        self.tp_rearm_floor = 0.0
        # Dashboard
        self.events = []                    # buffer pesan event penting (maks 4 baris)
        self.dashboard_lines = 0            # jumlah baris dashboard yang sedang tampil
        self._event_log = []                # untuk non-TTY: semua event (append-only, tidak rolling)
        self._last_event_count = 0          # indeks berikutnya yang belum dicetak di _event_log
        # Sesi
        self.session_number = 1             # nomor sesi saat ini (mulai dari 1, naik tiap auto-reset)
        self.session_start  = datetime.now() # waktu mulai sesi saat ini (direset saat auto-reset)
        self._pending_session_reset = False  # True = reset diterapkan di awal iterasi berikutnya

    @property
    def net_profit(self):
        """Profit bersih sejak bot mulai (balance sekarang − balance awal).
        Nilai ini selalu benar sepanjang sesi; take-profit rearm ditangani
        lewat tp_rearm_floor, bukan dengan mengubah initial_balance."""
        return self.balance - self.initial_balance

state = State()

# ==================== SIGNAL HANDLING ====================
# SIGTERM dikirim oleh `kill <pid>` di VPS — tangani sama seperti Ctrl+C
# agar bot berhenti dengan bersih (final stats dicetak, dashboard dihapus).
def _handle_sigterm(signum, frame):
    """Tandai bot agar berhenti di akhir iterasi berikutnya."""
    state.is_running = False

signal.signal(signal.SIGTERM, _handle_sigterm)

# ==================== ANSI COLORS ====================
# Kode warna terminal — otomatis dinonaktifkan jika output bukan TTY
_TTY  = sys.stdout.isatty()          # True jika output ke terminal langsung
_RST  = '\033[0m'   if _TTY else ''  # Reset warna
_BOLD = '\033[1m'   if _TTY else ''  # Tebal
_DIM  = '\033[2m'   if _TTY else ''  # Redup
_GRN  = '\033[92m'  if _TTY else ''  # Hijau terang  → profit / menang
_RED  = '\033[91m'  if _TTY else ''  # Merah terang  → rugi / kalah
_YLW  = '\033[93m'  if _TTY else ''  # Kuning terang → big win
_CYN  = '\033[96m'  if _TTY else ''  # Cyan          → info waktu

def _c(text, *codes):
    """Bungkus teks dengan satu atau lebih kode ANSI lalu reset."""
    return ''.join(codes) + str(text) + _RST

# ==================== LOG FILE ====================

_LOG_HEADER = 'timestamp,bet_id,amount,payout,multiplier,profit,balance\n'

def init_log_file():
    """Buat file log CSV dengan header jika belum ada. Cetak path-nya."""
    if not CONFIG['LOG_FILE']:
        return
    try:
        if not os.path.exists(CONFIG['LOG_FILE']):
            with open(CONFIG['LOG_FILE'], 'w', encoding='utf-8') as f:
                f.write(_LOG_HEADER)
        print(f"📄 Log  : {CONFIG['LOG_FILE']} (max {CONFIG['LOG_MAX_LINES']} baris, auto-trim)")
    except Exception as e:
        print(f"⚠️ Gagal buat log file: {e}")

def append_log(result: dict):
    """Tambah satu baris ke log. Tidak ada I/O jika LOG_FILE kosong."""
    if not CONFIG['LOG_FILE']:
        return
    try:
        ts  = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        amt = result.get('amount', 0)
        payout = amt + result.get('profit', 0)
        line = (
            f"{ts},"
            f"{result.get('bet_id', '')},"
            f"{amt:.2f},"
            f"{payout:.2f},"
            f"{result.get('multiplier', 0):.4f},"
            f"{result.get('profit', 0):.2f},"
            f"{result.get('balance', 0):.2f}\n"
        )
        with open(CONFIG['LOG_FILE'], 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass  # jangan sampai error log menghentikan bot

def trim_log_if_needed():
    """
    Potong log ke LOG_MAX_LINES baris data terakhir + header.
    Dipanggil setiap 100 bet agar I/O minimal dan tidak menghambat kecepatan.
    """
    if not CONFIG['LOG_FILE']:
        return
    try:
        with open(CONFIG['LOG_FILE'], 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # lines[0] = header, lines[1:] = data
        max_data = CONFIG['LOG_MAX_LINES']
        if len(lines) <= max_data + 1:
            return  # belum perlu trim
        trimmed = [lines[0]] + lines[-max_data:]
        with open(CONFIG['LOG_FILE'], 'w', encoding='utf-8') as f:
            f.writelines(trimmed)
    except Exception:
        pass

# ==================== LOGIKA STRATEGI ====================

def calculate_next_bet(last_profit: float) -> float:
    """
    Hitung nominal bet berikutnya berdasarkan hasil bet terakhir.

    FLAT          : selalu BET_AMOUNT.
    ANTI_MARTINGALE:
      - Menang  → lipat current_bet × BET_MULTIPLIER, maks WIN_STREAK_CAP kali lipat
                  dan tidak melampaui MAX_BET (jika diset).
      - Kalah   → reset ke BET_AMOUNT dasar.
    MARTINGALE:
      - Kalah   → lipat current_bet × BET_MULTIPLIER (kejar kerugian).
      - Menang  → reset ke BET_AMOUNT dasar.
      - LOSS_STREAK_CAP: jika setreak kalah mencapai cap, reset ke dasar (cut loss).
      - MAX_BET : batas atas nominal; jika terlampaui, reset setelah bet ini.
    """
    if CONFIG['STRATEGY'] == 'FLAT':
        # FLAT: tiap bet pakai base bet (acak jika MIN/MAX diisi)
        return get_base_bet()

    won = last_profit > 0

    if CONFIG['STRATEGY'] == 'ANTI_MARTINGALE':
        if won:
            state.win_streak += 1
            if state.win_streak >= CONFIG['WIN_STREAK_CAP']:
                # Streak menang mentok cap → reset ke base baru (acak)
                state.win_streak = 0
                return get_base_bet()
            next_bet = state.current_bet * CONFIG['BET_MULTIPLIER']
        else:
            # Kalah → reset ke base baru (acak)
            state.win_streak = 0
            return get_base_bet()

        if CONFIG['MAX_BET'] > 0 and next_bet > CONFIG['MAX_BET']:
            next_bet = CONFIG['MAX_BET']
            state.win_streak = 0
        return next_bet

    # MARTINGALE
    if won:
        # Menang → reset ke base baru (acak), bersihkan semua flag
        state.loss_streak = 0
        state.martingale_capped = False
        return get_base_bet()

    # Kalah ↓
    # Jika bet sebelumnya sudah di cap → satu siklus cukup, reset ke base baru (acak)
    if state.martingale_capped:
        state.loss_streak = 0
        state.martingale_capped = False
        return get_base_bet()

    state.loss_streak += 1

    # Cut-loss: streak kalah sudah mentok LOSS_STREAK_CAP → reset ke base baru (acak)
    if CONFIG['LOSS_STREAK_CAP'] > 0 and state.loss_streak >= CONFIG['LOSS_STREAK_CAP']:
        state.loss_streak = 0
        state.martingale_capped = False
        return get_base_bet()

    next_bet = state.current_bet * CONFIG['BET_MULTIPLIER']

    # Jika melampaui MAX_BET → bet di cap, tandai agar bet berikutnya reset ke base
    if CONFIG['MAX_BET'] > 0 and next_bet > CONFIG['MAX_BET']:
        state.martingale_capped = True
        return CONFIG['MAX_BET']

    return next_bet

# ==================== GRAPHQL QUERIES ====================
# Stake API: plinkoBet pakai argumen langsung (bukan wrapper input:{})
# currency & risk adalah enum lowercase: idr, low/medium/high
PLINKO_BET_MUTATION = """
mutation PlinkoBet($amount: Float!, $currency: CurrencyEnum!, $rows: Int!, $risk: CasinoGamePlinkoRiskEnum!) {
  plinkoBet(amount: $amount, currency: $currency, rows: $rows, risk: $risk) {
    id
    amount
    currency
    payout
    payoutMultiplier
    active
  }
}
"""

# Stake API: field user (bukan me), balance ada di balances[].payout.{amount,currency}
# Tidak ada argumen filter currency — filter di Python
BALANCE_QUERY = """
query GetBalance {
  user {
    id
    balances {
      available {
        amount
        currency
      }
    }
  }
}
"""

# ==================== HTTP SESSION ====================
# Satu Session di-reuse sepanjang sesi bot — menghindari TCP/TLS handshake
# baru di setiap request (hemat 100–300ms per bet).
_session = requests.Session()

# ==================== FUNGSI UTAMA ====================

def get_headers():
    """Membuat headers untuk request ke Stake API"""
    return {
        'Content-Type': 'application/json',
        'x-access-token': CONFIG['STAKE_API_TOKEN'],
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        ),
        'Origin': 'https://stake.com',
        'Referer': 'https://stake.com/',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
    }

def get_balance(silent=False):
    """
    Cek saldo dari akun Stake. Return balance atau None jika gagal.

    silent=False (default) → pesan error di-print ke terminal (dipakai saat startup).
    silent=True            → pesan error masuk event log dashboard (dipakai di dalam loop).
    """
    def _warn(msg):
        """Kirim pesan error ke tempat yang tepat sesuai konteks."""
        if silent:
            add_event(msg)
        else:
            print(msg)

    if not CONFIG['STAKE_API_TOKEN']:
        _warn("❌ STAKE_API_TOKEN tidak ditemukan!")
        return None

    try:
        response = _session.post(
            CONFIG['GRAPHQL_URL'],
            json={'query': BALANCE_QUERY},
            headers=get_headers(),
            timeout=10
        )

        if response.status_code != 200:
            if response.status_code == 403:
                _warn("⚠️ Balance: HTTP 403 — token expired, ambil token baru")
            else:
                _warn(f"⚠️ Balance: HTTP {response.status_code}")
            return None

        data = response.json()

        if 'errors' in data:
            error_msg = data['errors'][0].get('message', 'Unknown GraphQL error')
            _warn(f"⚠️ Balance: GraphQL error — {error_msg[:40]}")
            return None

        # Response: data.user.balances[].available.{amount, currency}
        # Filter sesuai currency yang dikonfigurasi (lowercase)
        balances = data.get('data', {}).get('user', {}).get('balances', [])
        target_currency = CONFIG['CURRENCY_ENUM']  # e.g. 'idr'
        for b in balances:
            available = b.get('available', {})
            if available.get('currency', '').lower() == target_currency:
                balance = float(available.get('amount', 0))
                state.balance = balance
                return balance

        _warn(f"⚠️ Saldo {CONFIG['CURRENCY']} tidak ditemukan di akun.")
        return None

    except requests.exceptions.Timeout:
        _warn("⚠️ Balance: timeout koneksi")
        return None
    except Exception as e:
        _warn(f"⚠️ Balance: {str(e)[:40]}")
        return None

def place_plinko_bet():
    """
    Melakukan satu taruhan Plinko menggunakan state.current_bet.
    Rate-limit retry dilakukan secara iteratif (bukan rekursif).
    Raise Exception jika gagal.
    """
    if not CONFIG['STAKE_API_TOKEN']:
        raise Exception('STAKE_API_TOKEN tidak ditemukan')

    # Stake API: argumen langsung (bukan wrapped di input:{})
    # currency & risk harus lowercase enum
    variables = {
        'amount': state.current_bet,
        'currency': CONFIG['CURRENCY_ENUM'],  # 'idr'
        'rows': CONFIG['ROWS'],
        'risk': CONFIG['RISK_ENUM'],          # 'low'/'medium'/'high'
    }

    rate_limit_retries = 0

    while True:
        try:
            response = _session.post(
                CONFIG['GRAPHQL_URL'],
                json={
                    'query': PLINKO_BET_MUTATION,
                    'variables': variables
                },
                headers=get_headers(),
                timeout=15
            )
        except requests.exceptions.Timeout:
            raise Exception('Timeout - koneksi lambat')
        except requests.exceptions.ConnectionError:
            raise Exception('Connection error - periksa internet')

        # Handle rate limit (429) - iteratif, bukan rekursif
        if response.status_code == 429:
            rate_limit_retries += 1
            if rate_limit_retries > CONFIG['MAX_RATE_LIMIT_RETRIES']:
                raise Exception(f'Rate limit: sudah retry {rate_limit_retries} kali, berhenti.')

            try:
                retry_after = int(response.headers.get('retry-after', 5))
            except (ValueError, TypeError):
                retry_after = 5
            wait_time = max(retry_after, 5)
            add_event(
                f"⚠️ Rate limit 429 — tunggu {wait_time}s "
                f"(retry {rate_limit_retries}/{CONFIG['MAX_RATE_LIMIT_RETRIES']})"
            )
            time.sleep(wait_time)
            continue  # ulangi request

        # Handle error HTTP lainnya
        if response.status_code != 200:
            raise Exception(f'HTTP {response.status_code}: {response.text[:200]}')

        data = response.json()

        # Cek error GraphQL
        if 'errors' in data:
            error_msg = data['errors'][0].get('message', 'Unknown GraphQL error')
            raise Exception(f'GraphQL Error: {error_msg}')

        # Ekstrak data bet — plinkoBet langsung adalah bet-nya (bukan nested)
        bet_data = data.get('data', {}).get('plinkoBet')
        if not bet_data:
            raise Exception('Invalid response structure: plinkoBet tidak ditemukan')

        # Update state
        state.total_bets += 1
        amount     = float(bet_data.get('amount', 0))
        payout_val = float(bet_data.get('payout', 0))
        profit     = payout_val - amount   # Stake tidak punya field 'profit', hitung sendiri
        state.total_wagered += amount

        result = {
            'bet_id':     bet_data.get('id'),
            'amount':     amount,
            'currency':   bet_data.get('currency', CONFIG['CURRENCY_ENUM']),
            'multiplier': float(bet_data.get('payoutMultiplier', 0)),
            'profit':     profit,
        }

        return result

def format_rupiah(amount):
    """Format angka ke Rupiah"""
    return f"Rp {amount:,.0f}".replace(',', '.')

def add_event(msg: str):
    """
    Simpan pesan event ke buffer rolling (maks 4 baris) untuk dashboard TTY.
    Untuk non-TTY, simpan juga ke _event_log (append-only) agar tidak ada
    yang terlewat — rolling buffer tidak bisa dipakai sebagai tracker posisi
    karena panjangnya selalu ≤ 4.
    """
    state.events.append(msg)          # tambah pesan baru ke rolling list
    if len(state.events) > 4:         # jaga agar tidak lebih dari 4
        state.events.pop(0)           # buang yang paling lama
    if not _TTY:
        state._event_log.append(msg)  # simpan semua event tanpa batas untuk non-TTY

def reset_session():
    """
    Reset statistik sesi tanpa menghentikan bot.
    Dipanggil otomatis saat SESSION_RESET_BETS atau SESSION_RESET_MINUTES tercapai.

    Yang direset  : initial_balance, total_bets, win_count, total_wagered,
                    start_time, session_start, tp_rearm_floor.
    Yang TIDAK direset: current_bet, win_streak, loss_streak
                        (strategi tetap berlanjut lintas sesi).
    """
    prev_bets  = state.total_bets
    prev_wins  = state.win_count
    prev_net   = state.net_profit
    net_sign   = '+' if prev_net >= 0 else ''
    win_rate   = (prev_wins / prev_bets * 100) if prev_bets > 0 else 0

    state.session_number   += 1
    state.initial_balance   = state.balance
    state.balance_initialized = True
    state.total_bets        = 0
    state.win_count         = 0
    state.total_wagered     = 0.0
    state.tp_rearm_floor    = 0.0
    state.start_time        = datetime.now()
    state.session_start     = datetime.now()
    state.dashboard_lines   = 0    # paksa dashboard cetak ulang dari awal

    summary = (
        f"🔄 Sesi {state.session_number - 1} selesai: "
        f"{prev_bets} bet  WR {win_rate:.0f}%  "
        f"P/L {net_sign}{format_rupiah(abs(prev_net))}"
    )
    # add_event mengirim ke _event_log; update_dashboard() mencetak ke stdout
    # (baik TTY maupun non-TTY) — tidak perlu print() langsung di sini.
    add_event(summary)


def print_periodic_summary():
    """
    Catat ringkasan berkala setiap SUMMARY_EVERY_BETS bet ke event log.
    TTY   : tampil di panel bawah dashboard saat render berikutnya.
    Non-TTY: dicetak oleh update_dashboard() melalui _event_log (tidak dobel).
    """
    bets     = state.total_bets
    wins     = state.win_count
    win_rate = (wins / bets * 100) if bets > 0 else 0
    net      = state.net_profit
    net_sign = '+' if net >= 0 else ''

    msg = (
        f"📊 [{bets} bet] "
        f"WR: {win_rate:.1f}% ({wins}/{bets})  "
        f"Net: {net_sign}{format_rupiah(abs(net))}  "
        f"Bal: {format_rupiah(state.balance)}"
    )
    add_event(msg)


def update_dashboard(result=None):
    """
    Render ulang blok statistik di posisi yang sama menggunakan ANSI
    cursor-up. Terminal tidak pernah scroll selama bot berjalan.

    Non-TTY (nohup/pipe): cetak satu baris teks polos per bet agar log
    file tetap bersih tanpa escape code cursor.

    Teknik TTY:
      1. Geser kursor ke atas sejumlah baris dashboard sebelumnya.
      2. Tulis ulang setiap baris (hapus dulu dengan \\033[2K).
    Hasilnya: dashboard selalu tampil di tempat yang sama, tidak bertambah.
    """
    # ── Mode non-TTY: satu baris plain-text per bet ─────────────────
    if not _TTY:
        if result:
            p     = result.get('profit', 0)
            m     = result.get('multiplier', 0)
            amt   = result.get('amount', 0)   # nominal bet yang benar-benar dieksekusi
            sign  = '+' if p >= 0 else ''
            net   = state.net_profit
            nsign = '+' if net >= 0 else ''
            wr    = (state.win_count / state.total_bets * 100) if state.total_bets > 0 else 0
            print(
                f"[{state.total_bets}] "
                f"bet={format_rupiah(amt)} "
                f"x{m:.2f} "
                f"p={sign}{format_rupiah(p)} "
                f"bal={format_rupiah(state.balance)} "
                f"net={nsign}{format_rupiah(net)} "
                f"wr={wr:.1f}%",
                flush=True
            )
        # Cetak hanya event yang belum pernah dicetak (gunakan _event_log,
        # bukan state.events yang rolling — panjangnya selalu ≤ 4 sehingga
        # _last_event_count akan mentok dan event baru tidak pernah tercetak)
        new_events = state._event_log[state._last_event_count:]
        for ev in new_events:
            print(ev, flush=True)
        state._last_event_count = len(state._event_log)
        return

    # ── Hitung nilai statistik ──────────────────────────────────────
    elapsed_sec = (datetime.now() - state.start_time).total_seconds()
    mins = int(elapsed_sec // 60)
    secs = int(elapsed_sec % 60)
    bpm  = (state.total_bets / elapsed_sec * 60) if elapsed_sec >= 5 else 0

    # Profit/rugi bersih dengan warna merah/hijau
    net      = state.net_profit
    net_sign = '+' if net >= 0 else ''
    net_col  = _GRN if net >= 0 else _RED
    net_str  = _c(f"{net_sign}{format_rupiah(abs(net))}", net_col, _BOLD)

    # Progress bar MAX_LOSS — bar merah menunjukkan seberapa dekat ke batas rugi
    loss_bar = ''
    if CONFIG['MAX_LOSS'] > 0:
        cur_loss  = max(0, -state.net_profit)    # kerugian saat ini (0 jika masih untung)
        pct_loss  = min(cur_loss / CONFIG['MAX_LOSS'], 1.0)
        bar_w     = 14
        filled    = int(pct_loss * bar_w)
        loss_bar  = (
            f"  {_c('█' * filled, _RED)}"        # bagian terpakai → merah
            f"{'░' * (bar_w - filled)}"
            f"  {pct_loss*100:.0f}%"
        )

    # Info hasil bet terakhir
    last_str = _c('—', _DIM)
    if result:
        p   = result.get('profit', 0)
        m   = result.get('multiplier', 0)
        p_s = f"{'+'if p>0 else ''}{format_rupiah(p)}"

        # Tampilan jackpot hanya aktif jika JACKPOT_STOP_MULTIPLIER dikonfigurasi.
        # Jika tidak diset (0), perlakukan seperti big win biasa (>= 10x).
        jackpot_thr = CONFIG['JACKPOT_STOP_MULTIPLIER']
        if jackpot_thr > 0 and m >= jackpot_thr:
            # Jackpot stop aktif dan terkena — tampil tebal kuning + event log
            last_str = _c(f"🚨 JACKPOT! x{m:.0f}  {p_s}", _BOLD, _YLW)
            add_event(_c(f"🚨 JACKPOT x{m:.0f} hit! Profit: {p_s}", _BOLD, _YLW))
        elif m >= 10:
            # Big win — kuning terang + masuk event log
            last_str = _c(f"🔥 BIG WIN! x{m:.2f}  {p_s}", _YLW)
            add_event(_c(f"🔥 x{m:.2f} kena! {p_s}", _YLW))
        elif p > 0:
            last_str = _c(f"{p_s}  (x{m:.2f})", _GRN)
        else:
            last_str = _c(f"{p_s}  (x{m:.2f})", _RED)

    # Streak strategi (ikon + jumlah beruntun)
    streak_str = ''
    if CONFIG['STRATEGY'] == 'MARTINGALE' and state.loss_streak > 0:
        streak_str = _c(
            f"{'💀'*min(state.loss_streak,5)} {state.loss_streak}× kalah", _RED
        )
    elif CONFIG['STRATEGY'] == 'ANTI_MARTINGALE' and state.win_streak > 0:
        streak_str = _c(
            f"{'🔥'*min(state.win_streak,5)} {state.win_streak}× menang", _GRN
        )

    # ── Bangun baris-baris dashboard ───────────────────────────────
    W   = 54                   # lebar pemisah
    SEP = '═' * W              # garis tebal (atas/bawah)
    DIV = '─' * W              # garis tipis (pemisah dalam)

    rows = []
    rows.append(SEP)
    rows.append(
        f"  {_c('🎰 PLINKO AUTO-BET', _BOLD)}"
        f"{'':>12}"
        f"{_c(f'{mins:02d}:{secs:02d}', _CYN, _BOLD)}"
        f"  {_c(f'{bpm:.0f}/min', _DIM)}"
    )
    rows.append(DIV)
    rows.append(f"  💳 Balance   : {_c(format_rupiah(state.balance), _BOLD)}")
    rows.append(f"  📈 Net P/L   : {net_str}")
    rows.append(f"  🎯 Wager     : {format_rupiah(state.total_wagered)}")
    if CONFIG['MAX_LOSS'] > 0:
        rows.append(f"  🛡️  Max Loss  : {format_rupiah(CONFIG['MAX_LOSS'])}{loss_bar}")
    rows.append(f"  🎲 Total Bet : {state.total_bets}")
    # Win rate live
    if state.total_bets > 0:
        wr     = state.win_count / state.total_bets * 100
        wr_col = _GRN if wr >= 50 else (_YLW if wr >= 40 else _RED)
        wr_str = _c(f"{wr:.1f}%  ({state.win_count}/{state.total_bets})", wr_col)
    else:
        wr_str = _c('—', _DIM)
    sesi_sfx = _c(f"  [Sesi #{state.session_number}]", _DIM) if state.session_number > 1 else ''
    rows.append(f"  📊 Win Rate  : {wr_str}{sesi_sfx}")
    rows.append(DIV)
    rows.append(f"  ⚡ Last      : {last_str}")
    rows.append(f"  💡 Next Bet  : {format_rupiah(state.current_bet)}  {streak_str}")
    rows.append(DIV)

    # Event log — selalu tampil 4 baris (kosong jika tidak ada event)
    event_buf = (state.events + ['', '', '', ''])[:4]
    for ev in event_buf:
        rows.append(f"  {ev}" if ev else '')

    rows.append(SEP)

    # ── Render: geser kursor ke atas lalu timpa baris per baris ────
    if state.dashboard_lines > 0:
        # Naik ke baris pertama dashboard yang sudah dicetak
        sys.stdout.write(f'\033[{state.dashboard_lines}A')

    state.dashboard_lines = len(rows)   # catat untuk iterasi berikutnya

    out = ''
    for row in rows:
        out += f'\r\033[2K{row}\n'      # \033[2K = hapus baris, lalu tulis ulang

    sys.stdout.write(out)
    sys.stdout.flush()

def clear_dashboard():
    """
    Hapus blok dashboard dari terminal agar pesan stop/error kritis
    bisa dicetak normal di bawahnya tanpa tumpang tindih.
    Non-TTY: tidak ada yang perlu dihapus, langsung return.
    """
    if not _TTY:
        state.dashboard_lines = 0
        return
    if state.dashboard_lines > 0:
        # Naik ke baris pertama, hapus setiap baris, kembali ke atas
        sys.stdout.write(f'\033[{state.dashboard_lines}A')
        for _ in range(state.dashboard_lines):
            sys.stdout.write('\r\033[2K\n')
        sys.stdout.write(f'\033[{state.dashboard_lines}A')
        state.dashboard_lines = 0
        sys.stdout.flush()

def take_profit_countdown(seconds):
    """
    Countdown sebelum stop saat Take Profit tercapai.
    User bisa tekan Ctrl+C untuk membatalkan dan lanjut bet.
    """
    print(f"\n💰 TAKE PROFIT tercapai! Bot berhenti dalam {seconds} detik...")
    if _TTY:
        print("   (Tekan Ctrl+C dalam countdown ini untuk LANJUT bet)\n")
    else:
        print("   (Kirim SIGINT ke proses untuk membatalkan countdown)\n")
    try:
        for remaining in range(seconds, 0, -1):
            print(f"\r   ⏳ Berhenti dalam {remaining:2d} detik...", end='', flush=True)
            time.sleep(1)
        print()  # newline setelah countdown
        return True  # konfirmasi berhenti
    except KeyboardInterrupt:
        clear_dashboard()
        print("\n▶️  Countdown dibatalkan, melanjutkan bet...\n")
        return False  # lanjut bet

def print_header():
    """Print header info"""
    print("\n" + "="*55)
    print("🎰  P L I N K O   A U T O - B E T")
    print("="*55)
    print(f"⚙️  Risk      : {CONFIG['RISK']}")
    print(f"📊 Rows      : {CONFIG['ROWS']}")
    # Tampilkan info bet dasar (tetap atau acak)
    if CONFIG['BET_AMOUNT_MIN'] > 0 and CONFIG['BET_AMOUNT_MAX'] > 0:
        print(f"💰 Bet Dasar : Rp {CONFIG['BET_AMOUNT_MIN']:.0f} – Rp {CONFIG['BET_AMOUNT_MAX']:.0f} (acak per siklus)")
    else:
        print(f"💰 Bet Dasar : {format_rupiah(CONFIG['BET_AMOUNT'])}")

    # Tampilkan info delay (tetap atau acak)
    if CONFIG['BASE_DELAY_MIN_MS'] > 0 and CONFIG['BASE_DELAY_MAX_MS'] > 0:
        print(f"⏱️  Delay     : {CONFIG['BASE_DELAY_MIN_MS']}–{CONFIG['BASE_DELAY_MAX_MS']}ms (acak)")
    else:
        print(f"⏱️  Delay     : {CONFIG['BASE_DELAY_MS']}ms")

    # Stop conditions
    if CONFIG['STOP_LOSS'] > 0:
        print(f"🛑 Stop Loss : {format_rupiah(CONFIG['STOP_LOSS'])} (saldo absolut)")
    if CONFIG['MAX_LOSS'] > 0:
        print(f"🛡️  Max Loss  : -{format_rupiah(CONFIG['MAX_LOSS'])} dari modal awal (relatif)")
    if CONFIG['TAKE_PROFIT'] > 0:
        print(f"✅ Take Profit: +{format_rupiah(CONFIG['TAKE_PROFIT'])} profit (delay {CONFIG['TAKE_PROFIT_DELAY_SEC']}s)")
    if CONFIG['JACKPOT_STOP_MULTIPLIER'] > 0:
        print(f"🚨 Jackpot Stop: langsung berhenti jika kena x{CONFIG['JACKPOT_STOP_MULTIPLIER']:.0f}+")
    # Info strategi
    if CONFIG['STRATEGY'] == 'FLAT':
        print(f"📐 Strategi  : FLAT (bet selalu tetap)")
    elif CONFIG['STRATEGY'] == 'ANTI_MARTINGALE':
        max_bet_str = format_rupiah(CONFIG['MAX_BET']) if CONFIG['MAX_BET'] > 0 else "tidak dibatas"
        print(f"📐 Strategi  : ANTI-MARTINGALE")
        print(f"   Pengali   : x{CONFIG['BET_MULTIPLIER']} saat menang")
        print(f"   Max lipat : {CONFIG['WIN_STREAK_CAP']}x berturut-turut lalu reset")
        print(f"   Max bet   : {max_bet_str}")
    elif CONFIG['STRATEGY'] == 'MARTINGALE':
        max_bet_str = format_rupiah(CONFIG['MAX_BET']) if CONFIG['MAX_BET'] > 0 else "tidak dibatas"
        loss_cap_str = f"{CONFIG['LOSS_STREAK_CAP']}x kalah lalu cut-loss" if CONFIG['LOSS_STREAK_CAP'] > 0 else "tidak dibatas"
        print(f"📐 Strategi  : MARTINGALE")
        print(f"   Pengali   : x{CONFIG['BET_MULTIPLIER']} saat kalah")
        print(f"   Cut-loss  : {loss_cap_str}")
        print(f"   Max bet   : {max_bet_str}")
        # Simulasi eskalasi bet — pakai bet dasar yang sebenarnya (min jika acak)
        sim_start = (
            CONFIG['BET_AMOUNT_MIN']
            if CONFIG['BET_AMOUNT_MIN'] > 0 and CONFIG['BET_AMOUNT_MAX'] > 0
            else CONFIG['BET_AMOUNT']
        )
        sim, steps = sim_start, []
        max_levels = CONFIG['LOSS_STREAK_CAP'] if CONFIG['LOSS_STREAK_CAP'] > 0 else 8
        for i in range(min(8, max_levels)):
            steps.append(format_rupiah(sim))
            next_sim = sim * CONFIG['BET_MULTIPLIER']
            if CONFIG['MAX_BET'] > 0 and next_sim > CONFIG['MAX_BET']:
                # Tampilkan cap bet hanya jika tidak ada LOSS_STREAK_CAP yang akan
                # memotong lebih awal — jika LOSS_STREAK_CAP=2 dan kita sudah di level 2,
                # bot reset lewat streak, bukan lewat cap, jadi cap tidak perlu ditampilkan.
                if CONFIG['LOSS_STREAK_CAP'] == 0:
                    steps.append(f"{format_rupiah(CONFIG['MAX_BET'])} (cap)")
                break
            sim = next_sim
        # Akhiri dengan '→ ...' jika unlimited, '→ reset' jika ada batas
        suffix = ' → ...' if CONFIG['LOSS_STREAK_CAP'] == 0 and len(steps) == 8 else ' → reset'
        print(f"   Eskalasi  : {' → '.join(steps)}{suffix}")
    print("="*55)

def check_stop_conditions():
    """
    Cek semua kondisi stop: take profit, stop loss, max loss, jackpot.
    Sebelum print pesan, dashboard dibersihkan agar tidak tumpang tindih.
    Return True jika harus berhenti.
    """
    # ── Take profit ─────────────────────────────────────────────────
    # Guard balance_initialized mencegah false positive sebelum saldo awal terisi.
    # Trigger ketika net_profit melampaui threshold saat ini (floor + TAKE_PROFIT).
    tp_threshold = state.tp_rearm_floor + CONFIG['TAKE_PROFIT']
    if CONFIG['TAKE_PROFIT'] > 0 and state.balance_initialized and state.net_profit >= tp_threshold:
        clear_dashboard()
        net_str    = format_rupiah(state.net_profit)
        target_str = format_rupiah(CONFIG['TAKE_PROFIT'])
        print(f"\n✅ TAKE PROFIT! Profit: +{net_str} (target: +{target_str})")
        print(f"   Saldo sekarang: {format_rupiah(state.balance)}")
        should_stop = take_profit_countdown(CONFIG['TAKE_PROFIT_DELAY_SEC'])
        if should_stop:
            return True
        # Countdown dibatalkan → naikkan floor agar trigger berikutnya butuh profit ekstra
        # sebesar TAKE_PROFIT lagi. initial_balance TIDAK disentuh.
        state.tp_rearm_floor = state.net_profit
        state.dashboard_lines = 0               # paksa dashboard cetak ulang dari awal
        return False

    # ── Stop loss absolut ────────────────────────────────────────────
    if CONFIG['STOP_LOSS'] > 0 and state.balance <= CONFIG['STOP_LOSS']:
        clear_dashboard()
        print(f"\n🛑 STOP LOSS tercapai!")
        print(f"   Saldo    : {format_rupiah(state.balance)}")
        print(f"   Threshold: {format_rupiah(CONFIG['STOP_LOSS'])}")
        return True

    # ── Max loss relatif ─────────────────────────────────────────────
    # Berhenti jika rugi >= MAX_LOSS dari modal awal sesi (independen dari saldo absolut)
    if CONFIG['MAX_LOSS'] > 0 and state.balance_initialized and (-state.net_profit) >= CONFIG['MAX_LOSS']:
        clear_dashboard()
        print(f"\n🛡️  MAX LOSS tercapai! Melindungi modal.")
        print(f"   Rugi sesi ini : {format_rupiah(-state.net_profit)}")
        print(f"   Batas rugi    : {format_rupiah(CONFIG['MAX_LOSS'])}")
        print(f"   Saldo sekarang: {format_rupiah(state.balance)}")
        return True

    return False

def print_final_stats():
    """Print statistik akhir setelah dashboard dibersihkan."""
    clear_dashboard()                            # hapus dashboard agar tidak tumpang tindih
    print("\n" + "="*55)
    print("📊  S T A T I S T I K   A K H I R")
    print("="*55)
    elapsed = datetime.now() - state.start_time
    minutes = int(elapsed.total_seconds() // 60)
    seconds = int(elapsed.total_seconds() % 60)

    print(f"⏱️  Durasi        : {minutes}m {seconds}s")
    print(f"🎯 Total Bets    : {state.total_bets}")
    print(f"💰 Total Wagered : {format_rupiah(state.total_wagered)}")
    print(f"💳 Final Balance : {format_rupiah(state.balance)}")

    if state.total_bets > 0:
        # Gunakan state.win_count yang ditrack per-bet (tidak perlu iterasi list)
        win_rate   = (state.win_count / state.total_bets) * 100
        net_profit = state.net_profit
        profit_str = f"+{format_rupiah(net_profit)}" if net_profit >= 0 else format_rupiah(net_profit)
        print(f"📈 Win Rate      : {win_rate:.1f}% ({state.win_count}/{state.total_bets})")
        print(f"💹 Net Profit    : {profit_str}")

    print("="*55)
    print("👋 Script selesai.")

def main():
    """Main loop"""
    print_header()

    # Validasi token
    if not CONFIG['STAKE_API_TOKEN']:
        print("\n❌ ERROR: STAKE_API_TOKEN tidak ditemukan!")
        print("📌 Buat file .env dan isi: STAKE_API_TOKEN=your_token_here")
        print("📌 Atau jalankan: bash setup.sh")
        print("📌 Cara dapat token: buka Stake.com → F12 → Network → cari x-access-token di request header")
        sys.exit(1)

    # Ambil saldo awal
    print("🔄 Mengambil saldo awal...")
    initial_balance = get_balance()
    if initial_balance is None:
        print("❌ Gagal mengambil saldo. Periksa token dan koneksi.")
        sys.exit(1)

    state.initial_balance = initial_balance
    state.balance_initialized = True
    print(f"✅ Saldo awal: {format_rupiah(initial_balance)} {CONFIG['CURRENCY']}")
    if CONFIG['TAKE_PROFIT'] > 0:
        target_balance = initial_balance + CONFIG['TAKE_PROFIT']
        print(f"🎯 Target saldo: {format_rupiah(target_balance)} (+{format_rupiah(CONFIG['TAKE_PROFIT'])})")

    if check_stop_conditions():
        print_final_stats()
        sys.exit(0)

    init_log_file()
    print("\n🚀 Memulai auto-bet... (tekan Ctrl+C untuk berhenti)\n")

    iteration = 0
    try:
        while state.is_running:

            # ── Deferred session reset ────────────────────────────────
            # Reset diterapkan di AWAL iterasi baru, bukan saat bet pemicu,
            # sehingga bet pemicu sudah selesai dirender sebelum counter-counter direset.
            if state._pending_session_reset:
                state._pending_session_reset = False
                reset_session()
                update_dashboard()          # render ulang segera dengan counter baru

            # ── Refresh balance & cek stop setiap 5 bet ──────────────
            if iteration > 0 and iteration % 10 == 0:
                fetched = get_balance(silent=True)   # error masuk event log, bukan print
                if fetched is None:
                    add_event("⚠️  Balance gagal diambil, pakai nilai terakhir")
                if check_stop_conditions():
                    state.is_running = False
                    break

            # ── Place bet ─────────────────────────────────────────────
            try:
                result = place_plinko_bet()
                state.consecutive_errors = 0   # reset counter error setelah bet sukses
            except Exception as e:
                state.consecutive_errors += 1
                err_short = str(e)[:50]         # potong pesan agar muat satu baris event
                add_event(
                    f"❌ Error #{state.total_bets+1}: {err_short} "
                    f"({state.consecutive_errors}/{CONFIG['MAX_CONSECUTIVE_ERRORS']})"
                )
                update_dashboard()              # refresh dashboard agar event error terlihat

                if state.consecutive_errors >= CONFIG['MAX_CONSECUTIVE_ERRORS']:
                    # Error terlalu banyak → bersihkan dashboard, print kritis, berhenti
                    clear_dashboard()
                    print("🛑 Terlalu banyak error berturut-turut. Menghentikan script.")
                    state.is_running = False
                    break

                # Verifikasi saldo setelah error (bet mungkin sudah masuk di server)
                add_event("⏳ Menunggu 5 detik lalu verifikasi saldo...")
                time.sleep(5)
                get_balance(silent=True)        # error masuk event log, bukan print
                continue                        # langsung retry, skip delay normal

            # ── Update state setelah bet sukses ───────────────────────
            # Hitung nominal bet berikutnya berdasarkan hasil saat ini
            state.current_bet = calculate_next_bet(result.get('profit', 0))

            # Catat win untuk statistik akhir
            if result.get('profit', 0) > 0:
                state.win_count += 1

            # Update balance lokal dari profit — tanpa HTTP tambahan
            # (API di-refresh setiap 5 bet di atas untuk akurasi stop-loss)
            state.balance += result.get('profit', 0)
            result['balance'] = state.balance

            # ── Ringkasan berkala ──────────────────────────────────────
            if (CONFIG['SUMMARY_EVERY_BETS'] > 0
                    and state.total_bets % CONFIG['SUMMARY_EVERY_BETS'] == 0):
                print_periodic_summary()

            # ── Auto-reset sesi ───────────────────────────────────────
            _reset_by_bets = (
                CONFIG['SESSION_RESET_BETS'] > 0
                and state.total_bets > 0
                and state.total_bets % CONFIG['SESSION_RESET_BETS'] == 0
            )
            _reset_by_time = (
                CONFIG['SESSION_RESET_MINUTES'] > 0
                and (datetime.now() - state.session_start).total_seconds()
                    >= CONFIG['SESSION_RESET_MINUTES'] * 60
            )
            if _reset_by_bets or _reset_by_time:
                state._pending_session_reset = True

            # ── Render dashboard & log ────────────────────────────────
            update_dashboard(result)            # gambar ulang dashboard di tempat yang sama
            append_log(result)                  # tulis ke file CSV

            # Trim log setiap 100 bet agar file tidak membengkak
            if state.total_bets % 100 == 0:
                trim_log_if_needed()

            # ── Jackpot stop — cek SEBELUM stop conditions biasa ─────
            # Jika multiplier >= JACKPOT_STOP_MULTIPLIER → kunci profit, berhenti LANGSUNG
            # tanpa countdown (tidak bisa dibatalkan). Ini melindungi kemenangan besar.
            m = result.get('multiplier', 0)
            jstop = CONFIG['JACKPOT_STOP_MULTIPLIER']
            if jstop > 0 and m >= jstop:
                clear_dashboard()
                print(f"\n🚨 JACKPOT x{m:.0f} TERKENA! Profit dikunci, bot berhenti.")
                print(f"   Profit sesi  : +{format_rupiah(state.net_profit)}")
                print(f"   Saldo sekarang: {format_rupiah(state.balance)}")
                state.is_running = False
                break

            # ── Cek kondisi berhenti biasa ────────────────────────────
            if check_stop_conditions():
                state.is_running = False
                break

            # ── Delay acak sebelum bet berikutnya ─────────────────────
            # Jika BASE_DELAY_MIN_MS & BASE_DELAY_MAX_MS diisi → delay random di antara keduanya
            # (mencegah pola interval tetap yang mudah dideteksi server)
            if CONFIG['BASE_DELAY_MIN_MS'] > 0 and CONFIG['BASE_DELAY_MAX_MS'] > 0:
                delay_ms = random.randint(CONFIG['BASE_DELAY_MIN_MS'], CONFIG['BASE_DELAY_MAX_MS'])
            else:
                delay_ms = CONFIG['BASE_DELAY_MS']
            time.sleep(delay_ms / 1000.0)
            iteration += 1

    except KeyboardInterrupt:
        clear_dashboard()                       # bersihkan dashboard sebelum pesan berhenti
        print("\n⏹️  Script dihentikan oleh user (Ctrl+C)")

    print_final_stats()

if __name__ == "__main__":
    main()
