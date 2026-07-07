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
CONFIG = {
    # API Token dari Stake.com
    'STAKE_API_TOKEN': os.getenv('STAKE_API_TOKEN', ''),
    
    # Pengaturan Game
    'RISK': 'LOW',
    'ROWS': 8,
    'BET_AMOUNT': 500,  # 500 IDR
    'CURRENCY': 'IDR',
    
    # Delay antar bet (ms)
    'BASE_DELAY_MS': 200,
    
    # Stop Loss (dalam IDR) - berhenti jika saldo turun ke angka ini
    'STOP_LOSS': float(os.getenv('STOP_LOSS', '10000')),  # default 10,000 IDR
    
    # Target wager (opsional, 0 = unlimited)
    'WAGER_TARGET': float(os.getenv('WAGER_TARGET', '0')),
    
    # GraphQL Endpoint
    'GRAPHQL_URL': 'https://stake.com/_api/graphql',
}

# ==================== STATE ====================
class State:
    def __init__(self):
        self.balance = 0
        self.total_wagered = 0
        self.total_bets = 0
        self.is_running = True
        self.rate_limit_retries = 0
        self.consecutive_errors = 0
        self.start_time = datetime.now()
        self.bet_results = []

state = State()

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
query GetBalance {
  me {
    id
    balances(currency: "IDR") {
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

def get_balance():
    """Cek saldo IDR dari akun Stake"""
    if not CONFIG['STAKE_API_TOKEN']:
        print("❌ STAKE_API_TOKEN tidak ditemukan!")
        return 0

    try:
        response = requests.post(
            CONFIG['GRAPHQL_URL'],
            json={'query': BALANCE_QUERY},
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            balances = data.get('data', {}).get('me', {}).get('balances', [])
            if balances:
                balance = float(balances[0].get('amount', 0))
                state.balance = balance
                return balance
        else:
            print(f"⚠️ Gagal cek balance: HTTP {response.status_code}")
            return state.balance or 0
            
    except Exception as e:
        print(f"⚠️ Error cek balance: {str(e)}")
        return state.balance or 0

def place_plinko_bet():
    """Melakukan satu taruhan Plinko"""
    if not CONFIG['STAKE_API_TOKEN']:
        raise Exception('STAKE_API_TOKEN tidak ditemukan')

    variables = {
        'input': {
            'risk': CONFIG['RISK'],
            'rows': CONFIG['ROWS'],
            'amount': CONFIG['BET_AMOUNT'],
            'currency': CONFIG['CURRENCY'],
        }
    }

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

        # Handle rate limit (429)
        if response.status_code == 429:
            retry_after = int(response.headers.get('retry-after', 5))
            wait_time = max(retry_after, 5)
            
            state.rate_limit_retries += 1
            print(f"\n⚠️ Rate limit (429) terdeteksi. Menunggu {wait_time} detik... (retry #{state.rate_limit_retries})")
            time.sleep(wait_time)
            
            if state.rate_limit_retries <= 10:
                return place_plinko_bet()
            else:
                raise Exception('Terlalu banyak rate limit retry')

        # Handle error lainnya
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
            raise Exception('Invalid response structure')

        # Update state
        bet = bet_data.get('bet', {})
        state.total_bets += 1
        state.total_wagered += float(bet.get('amount', 0))
        
        # Update balance jika ada
        if 'balance' in bet_data:
            state.balance = float(bet_data.get('balance', {}).get('amount', state.balance))

        # Reset error counter
        state.consecutive_errors = 0
        state.rate_limit_retries = 0

        # Simpan hasil
        result = {
            'bet_id': bet.get('id'),
            'amount': float(bet.get('amount', 0)),
            'currency': bet.get('currency', 'IDR'),
            'multiplier': float(bet.get('payoutMultiplier', 0)),
            'profit': float(bet.get('profit', 0)),
            'balance': state.balance,
        }
        state.bet_results.append(result)
        
        return result

    except requests.exceptions.Timeout:
        raise Exception('Timeout - koneksi lambat')
    except requests.exceptions.ConnectionError:
        raise Exception('Connection error - periksa internet')
    except Exception as e:
        raise Exception(f'Error: {str(e)}')

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
    
    # Status message
    status = f"🎯 Bets: {state.total_bets} | Wager: {wagered_str} | Balance: {balance_str} | Time: {minutes}m{seconds}s"
    
    if result:
        profit = result.get('profit', 0)
        multiplier = result.get('multiplier', 0)
        profit_str = f"+{format_rupiah(profit)}" if profit > 0 else format_rupiah(profit)
        status += f" | Last: {profit_str} (x{multiplier:.2f})"
    
    if state.rate_limit_retries > 0:
        status += f" | ⚠️ Retry: {state.rate_limit_retries}x"
    
    # Print dengan carriage return untuk update di baris yang sama
    print(f"\r{status}", end='', flush=True)

def clear_line():
    """Clear current console line"""
    sys.stdout.write('\033[2K\r')
    sys.stdout.flush()

def print_header():
    """Print header info"""
    print("\n" + "="*50)
    print("🎰 P L I N K O   A U T O - B E T")
    print("="*50)
    print(f"⚙️  Risk: {CONFIG['RISK']}")
    print(f"📊 Rows: {CONFIG['ROWS']}")
    print(f"💰 Bet: {format_rupiah(CONFIG['BET_AMOUNT'])}")
    print(f"🛑 Stop Loss: {format_rupiah(CONFIG['STOP_LOSS'])}")
    print(f"⏱️  Delay: {CONFIG['BASE_DELAY_MS']}ms")
    print("="*50)

def main():
    """Main loop"""
    print_header()
    
    # Cek token
    if not CONFIG['STAKE_API_TOKEN']:
        print("\n❌ ERROR: STAKE_API_TOKEN tidak ditemukan!")
        print("📌 Buat file .env dan isi: STAKE_API_TOKEN=your_token_here")
        print("📌 Cara dapat token: buka Stake.com → F12 → Network → cari request ke _api")
        sys.exit(1)
    
    # Ambil saldo awal
    print("🔄 Mengambil saldo awal...")
    initial_balance = get_balance()
    print(f"✅ Saldo awal: {format_rupiah(initial_balance)} IDR")
    
    if initial_balance <= CONFIG['STOP_LOSS']:
        print(f"\n❌ Stop Loss tercapai!")
        print(f"   Saldo: {format_rupiah(initial_balance)}")
        print(f"   Threshold: {format_rupiah(CONFIG['STOP_LOSS'])}")
        sys.exit(0)
    
    print("\n🚀 Memulai auto-bet... (tekan Ctrl+C untuk berhenti)\n")
    
    # Main loop
    iteration = 0
    try:
        while state.is_running:
            # Cek stop loss setiap 5 bets
            if iteration > 0 and iteration % 5 == 0:
                get_balance()
                if state.balance <= CONFIG['STOP_LOSS']:
                    clear_line()
                    print(f"\n🛑 STOP LOSS tercapai!")
                    print(f"   Saldo: {format_rupiah(state.balance)}")
                    print(f"   Threshold: {format_rupiah(CONFIG['STOP_LOSS'])}")
                    state.is_running = False
                    break
            
            # Cek wager target
            if CONFIG['WAGER_TARGET'] > 0 and state.total_wagered >= CONFIG['WAGER_TARGET']:
                clear_line()
                print(f"\n🎯 Wager target tercapai!")
                print(f"   Total wagered: {format_rupiah(state.total_wagered)}")
                state.is_running = False
                break
            
            # Place bet
            result = place_plinko_bet()
            update_status(result)
            
            # Delay
            time.sleep(CONFIG['BASE_DELAY_MS'] / 1000.0)
            iteration += 1
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Script dihentikan oleh user (Ctrl+C)")
    except Exception as e:
        clear_line()
        print(f"\n❌ Error: {str(e)}")
        state.consecutive_errors += 1
        
        if state.consecutive_errors > 5:
            print("🛑 Terlalu banyak error. Menghentikan script.")
            state.is_running = False
        else:
            print(f"⏳ Retry dalam 5 detik... ({state.consecutive_errors}/5)")
            time.sleep(5)
            if state.is_running:
                return main()  # Restart loop
    
    # Final statistics
    print("\n" + "="*50)
    print("📊 S T A T I S T I K   A K H I R")
    print("="*50)
    elapsed = datetime.now() - state.start_time
    minutes = int(elapsed.total_seconds() // 60)
    seconds = int(elapsed.total_seconds() % 60)
    
    print(f"⏱️  Durasi: {minutes}m {seconds}s")
    print(f"🎯 Total Bets: {state.total_bets}")
    print(f"💰 Total Wagered: {format_rupiah(state.total_wagered)}")
    print(f"💳 Final Balance: {format_rupiah(state.balance)}")
    
    if state.total_bets > 0:
        win_count = sum(1 for r in state.bet_results if r.get('profit', 0) > 0)
        win_rate = (win_count / state.total_bets) * 100
        print(f"📈 Win Rate: {win_rate:.1f}% ({win_count}/{state.total_bets})")
    
    print("="*50)
    print("👋 Script selesai.")

if __name__ == "__main__":
    main()
