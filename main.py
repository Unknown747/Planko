#!/usr/bin/env python3
# main.py - Auto Bet Plinko Stake.com
import requests
import json
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

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

    rows = get_int('ROWS', 8)
    if rows not in VALID_ROWS:
        errors.append(f"ROWS={rows} tidak valid. Pilihan: 8 hingga 16.")

    bet_amount = get_float('BET_AMOUNT', 500)
    if bet_amount <= 0:
        errors.append(f"BET_AMOUNT={bet_amount} harus lebih dari 0.")

    base_delay = get_int('BASE_DELAY_MS', 200)
    if base_delay < 0:
        errors.append(f"BASE_DELAY_MS={base_delay} tidak boleh negatif.")

    stop_loss = get_float('STOP_LOSS', 10000)
    if stop_loss < 0:
        errors.append(f"STOP_LOSS={stop_loss} tidak boleh negatif.")

    wager_target = get_float('WAGER_TARGET', 0)
    if wager_target < 0:
        errors.append(f"WAGER_TARGET={wager_target} tidak boleh negatif.")

    take_profit = get_float('TAKE_PROFIT', 0)
    if take_profit < 0:
        errors.append(f"TAKE_PROFIT={take_profit} tidak boleh negatif.")

    take_profit_delay = get_int('TAKE_PROFIT_DELAY_SEC', 30)
    if take_profit_delay < 0:
        errors.append(f"TAKE_PROFIT_DELAY_SEC={take_profit_delay} tidak boleh negatif.")

    # --- Strategi betting ---
    valid_strategies = {'FLAT', 'ANTI_MARTINGALE'}
    strategy = os.getenv('STRATEGY', 'FLAT').upper()
    if strategy not in valid_strategies:
        errors.append(f"STRATEGY='{strategy}' tidak valid. Pilihan: FLAT, ANTI_MARTINGALE.")

    bet_multiplier = get_float('BET_MULTIPLIER', 2.0)
    if bet_multiplier <= 1.0:
        errors.append(f"BET_MULTIPLIER={bet_multiplier} harus lebih dari 1 (contoh: 2).")

    win_streak_cap = get_int('WIN_STREAK_CAP', 3)
    if win_streak_cap < 1:
        errors.append(f"WIN_STREAK_CAP={win_streak_cap} harus minimal 1.")

    max_bet = get_float('MAX_BET', 0)  # 0 = tidak ada batas
    if max_bet < 0:
        errors.append(f"MAX_BET={max_bet} tidak boleh negatif.")

    max_errors = get_int('MAX_CONSECUTIVE_ERRORS', 5)
    if max_errors < 1:
        errors.append(f"MAX_CONSECUTIVE_ERRORS={max_errors} harus minimal 1.")

    max_retries = get_int('MAX_RATE_LIMIT_RETRIES', 10)
    if max_retries < 1:
        errors.append(f"MAX_RATE_LIMIT_RETRIES={max_retries} harus minimal 1.")

    if errors:
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        raise ValueError(f"\nKesalahan konfigurasi .env:\n{msg}\n\nPerbaiki file .env lalu jalankan ulang.")

    return {
        'STAKE_API_TOKEN': os.getenv('STAKE_API_TOKEN', ''),
        'RISK': risk,
        'ROWS': rows,
        'BET_AMOUNT': bet_amount,       # bet dasar (selalu jadi acuan reset)
        'CURRENCY': os.getenv('CURRENCY', 'IDR'),
        'BASE_DELAY_MS': base_delay,
        'STOP_LOSS': stop_loss,
        'WAGER_TARGET': wager_target,
        'TAKE_PROFIT': take_profit,
        'TAKE_PROFIT_DELAY_SEC': take_profit_delay,
        'STRATEGY': strategy,
        'BET_MULTIPLIER': bet_multiplier,
        'WIN_STREAK_CAP': win_streak_cap,
        'MAX_BET': max_bet,
        'MAX_CONSECUTIVE_ERRORS': max_errors,
        'MAX_RATE_LIMIT_RETRIES': max_retries,
        'GRAPHQL_URL': os.getenv('GRAPHQL_URL', 'https://stake.com/_api/graphql'),
    }

try:
    CONFIG = _parse_env()
except ValueError as _cfg_err:
    print(_cfg_err)
    sys.exit(1)

# ==================== STATE ====================
class State:
    def __init__(self):
        self.balance = 0.0
        self.initial_balance = 0.0   # diset setelah get_balance() pertama
        self.total_wagered = 0.0
        self.total_bets = 0
        self.is_running = True
        self.consecutive_errors = 0
        self.start_time = datetime.now()
        self.bet_results = []
        # Strategi
        self.current_bet = CONFIG['BET_AMOUNT']  # bet aktif saat ini
        self.win_streak = 0                       # berapa kali menang berturut-turut

    @property
    def net_profit(self):
        """Profit bersih sejak bot mulai (balance sekarang - balance awal)."""
        return self.balance - self.initial_balance

state = State()

# ==================== LOGIKA STRATEGI ====================

def calculate_next_bet(last_profit: float) -> float:
    """
    Hitung nominal bet berikutnya berdasarkan hasil bet terakhir.

    FLAT        : selalu BET_AMOUNT.
    ANTI_MARTINGALE:
      - Menang  → lipat current_bet × BET_MULTIPLIER, maks WIN_STREAK_CAP kali lipat
                  dan tidak melampaui MAX_BET (jika diset).
      - Kalah   → reset ke BET_AMOUNT dasar.
    """
    if CONFIG['STRATEGY'] == 'FLAT':
        return CONFIG['BET_AMOUNT']

    # ANTI_MARTINGALE
    won = last_profit > 0
    if won:
        state.win_streak += 1
        if state.win_streak >= CONFIG['WIN_STREAK_CAP']:
            # Sudah mentok cap → reset (ambil profit, mulai lagi dari bawah)
            state.win_streak = 0
            return CONFIG['BET_AMOUNT']
        next_bet = state.current_bet * CONFIG['BET_MULTIPLIER']
    else:
        state.win_streak = 0
        return CONFIG['BET_AMOUNT']

    # Terapkan MAX_BET jika diset
    if CONFIG['MAX_BET'] > 0 and next_bet > CONFIG['MAX_BET']:
        next_bet = CONFIG['MAX_BET']
        state.win_streak = 0  # anggap sudah cap, reset setelah bet ini

    return next_bet

# ==================== GRAPHQL QUERIES ====================
PLINKO_BET_MUTATION = """
mutation PlinkoBet($input: PlinkoBetInput!) {
  plinkoBet(input: $input) {
    id
    gameId
    bet {
      id
      amount
      currency
      payoutMultiplier
      profit
      status
    }
    active
  }
}
"""

BALANCE_QUERY = """
query GetBalance($currency: CurrencyEnum!) {
  me {
    id
    balances(currency: $currency) {
      currency
      amount
    }
  }
}
"""

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

def get_balance():
    """Cek saldo dari akun Stake. Return balance atau None jika gagal."""
    if not CONFIG['STAKE_API_TOKEN']:
        print("❌ STAKE_API_TOKEN tidak ditemukan!")
        return None

    try:
        response = requests.post(
            CONFIG['GRAPHQL_URL'],
            json={
                'query': BALANCE_QUERY,
                'variables': {'currency': CONFIG['CURRENCY']},
            },
            headers=get_headers(),
            timeout=10
        )

        if response.status_code != 200:
            if response.status_code == 403:
                print("⚠️ HTTP 403: Token ditolak server.")
                print("   → Token mungkin sudah expired. Ambil token baru dari browser.")
                print("   → Buka Stake.com → F12 → Network → cari x-access-token di request header.")
            else:
                print(f"⚠️ Gagal cek balance: HTTP {response.status_code}")
            return None

        data = response.json()

        if 'errors' in data:
            error_msg = data['errors'][0].get('message', 'Unknown GraphQL error')
            print(f"⚠️ GraphQL error saat cek balance: {error_msg}")
            return None

        balances = data.get('data', {}).get('me', {}).get('balances', [])
        if balances:
            balance = float(balances[0].get('amount', 0))
            state.balance = balance
            return balance

        print("⚠️ Respons balance kosong.")
        return None

    except requests.exceptions.Timeout:
        print("⚠️ Timeout saat cek balance.")
        return None
    except Exception as e:
        print(f"⚠️ Error cek balance: {str(e)}")
        return None

def place_plinko_bet():
    """
    Melakukan satu taruhan Plinko menggunakan state.current_bet.
    Rate-limit retry dilakukan secara iteratif (bukan rekursif).
    Raise Exception jika gagal.
    """
    if not CONFIG['STAKE_API_TOKEN']:
        raise Exception('STAKE_API_TOKEN tidak ditemukan')

    variables = {
        'input': {
            'risk': CONFIG['RISK'],
            'rows': CONFIG['ROWS'],
            'amount': state.current_bet,   # pakai bet aktif dari state
            'currency': CONFIG['CURRENCY'],
        }
    }

    rate_limit_retries = 0

    while True:
        try:
            response = requests.post(
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

            retry_after = int(response.headers.get('retry-after', 5))
            wait_time = max(retry_after, 5)
            print(f"\n⚠️ Rate limit (429). Menunggu {wait_time}s... (retry #{rate_limit_retries}/{CONFIG['MAX_RATE_LIMIT_RETRIES']})")
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

        # Ekstrak data bet
        bet_data = data.get('data', {}).get('plinkoBet')
        if not bet_data:
            raise Exception('Invalid response structure: plinkoBet tidak ditemukan')

        bet = bet_data.get('bet', {})
        if not bet:
            raise Exception('Invalid response structure: bet tidak ditemukan')

        # Update state
        state.total_bets += 1
        amount = float(bet.get('amount', 0))
        state.total_wagered += amount

        result = {
            'bet_id': bet.get('id'),
            'amount': amount,
            'currency': bet.get('currency', CONFIG['CURRENCY']),
            'multiplier': float(bet.get('payoutMultiplier', 0)),
            'profit': float(bet.get('profit', 0)),
            'balance': state.balance,  # balance diupdate dari get_balance()
        }
        state.bet_results.append(result)

        return result

def format_rupiah(amount):
    """Format angka ke Rupiah"""
    return f"Rp {amount:,.0f}".replace(',', '.')

def update_status(result=None):
    """Update status di konsol (baris yang sama)"""
    elapsed = datetime.now() - state.start_time
    minutes = int(elapsed.total_seconds() // 60)
    seconds = int(elapsed.total_seconds() % 60)

    balance_str = format_rupiah(state.balance)
    wagered_str = format_rupiah(state.total_wagered)

    status = (
        f"🎯 Bets: {state.total_bets} | "
        f"Wager: {wagered_str} | "
        f"Balance: {balance_str} | "
        f"Time: {minutes}m{seconds}s"
    )

    if result:
        profit = result.get('profit', 0)
        multiplier = result.get('multiplier', 0)
        profit_str = f"+{format_rupiah(profit)}" if profit > 0 else format_rupiah(profit)
        status += f" | Last: {profit_str} (x{multiplier:.2f})"

    # Tampilkan info strategi Anti-Martingale
    if CONFIG['STRATEGY'] == 'ANTI_MARTINGALE':
        streak_bar = "🔥" * state.win_streak if state.win_streak > 0 else "·"
        status += f" | Bet: {format_rupiah(state.current_bet)} {streak_bar}"

    print(f"\r{status}", end='', flush=True)

def clear_line():
    """Clear current console line"""
    sys.stdout.write('\033[2K\r')
    sys.stdout.flush()

def take_profit_countdown(seconds):
    """
    Countdown sebelum stop saat Take Profit tercapai.
    User bisa tekan Ctrl+C untuk membatalkan dan lanjut bet.
    """
    print(f"\n💰 TAKE PROFIT tercapai! Bot berhenti dalam {seconds} detik...")
    print("   (Tekan Ctrl+C dalam countdown ini untuk LANJUT bet)\n")
    try:
        for remaining in range(seconds, 0, -1):
            print(f"\r   ⏳ Berhenti dalam {remaining:2d} detik...", end='', flush=True)
            time.sleep(1)
        print()  # newline setelah countdown
        return True  # konfirmasi berhenti
    except KeyboardInterrupt:
        clear_line()
        print("\n▶️  Countdown dibatalkan, melanjutkan bet...\n")
        return False  # lanjut bet

def print_header():
    """Print header info"""
    print("\n" + "="*55)
    print("🎰  P L I N K O   A U T O - B E T")
    print("="*55)
    print(f"⚙️  Risk      : {CONFIG['RISK']}")
    print(f"📊 Rows      : {CONFIG['ROWS']}")
    print(f"💰 Bet Dasar : {format_rupiah(CONFIG['BET_AMOUNT'])}")
    print(f"🛑 Stop Loss : {format_rupiah(CONFIG['STOP_LOSS'])}")
    if CONFIG['TAKE_PROFIT'] > 0:
        print(f"✅ Take Profit: +{format_rupiah(CONFIG['TAKE_PROFIT'])} profit (delay {CONFIG['TAKE_PROFIT_DELAY_SEC']}s)")
    if CONFIG['WAGER_TARGET'] > 0:
        print(f"🎯 Wager Target: {format_rupiah(CONFIG['WAGER_TARGET'])}")
    print(f"⏱️  Delay     : {CONFIG['BASE_DELAY_MS']}ms")
    # Info strategi
    if CONFIG['STRATEGY'] == 'FLAT':
        print(f"📐 Strategi  : FLAT (bet selalu tetap)")
    elif CONFIG['STRATEGY'] == 'ANTI_MARTINGALE':
        max_bet_str = format_rupiah(CONFIG['MAX_BET']) if CONFIG['MAX_BET'] > 0 else "tidak dibatas"
        print(f"📐 Strategi  : ANTI-MARTINGALE")
        print(f"   Pengali   : x{CONFIG['BET_MULTIPLIER']} saat menang")
        print(f"   Max lipat : {CONFIG['WIN_STREAK_CAP']}x berturut-turut lalu reset")
        print(f"   Max bet   : {max_bet_str}")
    print("="*55)

def check_stop_conditions():
    """
    Cek semua kondisi stop: take profit, stop loss, wager target.
    Return True jika harus berhenti.
    """
    # Take profit — cek lebih dahulu (kondisi positif)
    if CONFIG['TAKE_PROFIT'] > 0 and state.net_profit >= CONFIG['TAKE_PROFIT']:
        clear_line()
        net_str = format_rupiah(state.net_profit)
        target_str = format_rupiah(CONFIG['TAKE_PROFIT'])
        print(f"\n✅ TAKE PROFIT! Profit: +{net_str} (target: +{target_str})")
        print(f"   Saldo sekarang: {format_rupiah(state.balance)}")
        should_stop = take_profit_countdown(CONFIG['TAKE_PROFIT_DELAY_SEC'])
        if should_stop:
            return True
        # Jika dibatalkan, geser target +TAKE_PROFIT agar tidak langsung trigger lagi
        # (tetap di posisi profit saat ini sebagai baseline baru)
        state.initial_balance = state.balance - CONFIG['TAKE_PROFIT'] + 1
        return False

    # Wager target
    if CONFIG['WAGER_TARGET'] > 0 and state.total_wagered >= CONFIG['WAGER_TARGET']:
        clear_line()
        print(f"\n🎯 Wager target tercapai!")
        print(f"   Total wagered: {format_rupiah(state.total_wagered)}")
        return True

    # Stop loss
    if CONFIG['STOP_LOSS'] > 0 and state.balance > 0 and state.balance <= CONFIG['STOP_LOSS']:
        clear_line()
        print(f"\n🛑 STOP LOSS tercapai!")
        print(f"   Saldo    : {format_rupiah(state.balance)}")
        print(f"   Threshold: {format_rupiah(CONFIG['STOP_LOSS'])}")
        return True

    return False

def print_final_stats():
    """Print statistik akhir"""
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
        win_count = sum(1 for r in state.bet_results if r.get('profit', 0) > 0)
        win_rate = (win_count / state.total_bets) * 100
        net_profit = sum(r.get('profit', 0) for r in state.bet_results)
        profit_str = f"+{format_rupiah(net_profit)}" if net_profit >= 0 else format_rupiah(net_profit)
        print(f"📈 Win Rate      : {win_rate:.1f}% ({win_count}/{state.total_bets})")
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
    print(f"✅ Saldo awal: {format_rupiah(initial_balance)} {CONFIG['CURRENCY']}")
    if CONFIG['TAKE_PROFIT'] > 0:
        target_balance = initial_balance + CONFIG['TAKE_PROFIT']
        print(f"🎯 Target saldo: {format_rupiah(target_balance)} (+{format_rupiah(CONFIG['TAKE_PROFIT'])})")

    if check_stop_conditions():
        print_final_stats()
        sys.exit(0)

    print("\n🚀 Memulai auto-bet... (tekan Ctrl+C untuk berhenti)\n")

    iteration = 0
    try:
        while state.is_running:
            # Cek stop conditions setiap 5 bet (dan update balance)
            if iteration > 0 and iteration % 5 == 0:
                fetched = get_balance()
                if fetched is None:
                    print("\n⚠️ Gagal fetch balance, menggunakan nilai terakhir.")
                if check_stop_conditions():
                    state.is_running = False
                    break

            # Place bet
            try:
                result = place_plinko_bet()
                state.consecutive_errors = 0  # reset setelah bet berhasil
            except Exception as e:
                state.consecutive_errors += 1
                clear_line()
                print(f"\n❌ Error bet #{state.total_bets + 1}: {str(e)}")
                print(f"   Consecutive errors: {state.consecutive_errors}/{CONFIG['MAX_CONSECUTIVE_ERRORS']}")

                if state.consecutive_errors >= CONFIG['MAX_CONSECUTIVE_ERRORS']:
                    print("🛑 Terlalu banyak error berturut-turut. Menghentikan script.")
                    state.is_running = False
                    break

                print(f"⏳ Menunggu 5 detik sebelum retry...")
                time.sleep(5)
                continue  # skip delay normal, langsung retry

            # Hitung bet berikutnya berdasarkan hasil (sebelum refresh balance)
            state.current_bet = calculate_next_bet(result.get('profit', 0))

            # Refresh balance setelah setiap bet agar stop-loss akurat
            fetched = get_balance()
            if fetched is None:
                # Estimasi dari profit bet terakhir supaya tidak buta sama sekali
                state.balance += result.get('profit', 0)

            result['balance'] = state.balance
            update_status(result)

            if check_stop_conditions():
                state.is_running = False
                break

            # Delay antar bet
            time.sleep(CONFIG['BASE_DELAY_MS'] / 1000.0)
            iteration += 1

    except KeyboardInterrupt:
        print("\n\n⏹️  Script dihentikan oleh user (Ctrl+C)")

    print_final_stats()

if __name__ == "__main__":
    main()
