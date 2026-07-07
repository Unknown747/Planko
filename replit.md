# Plinko Auto-Bet — Stake.com

Bot Python untuk melakukan auto-bet pada game Plinko di Stake.com via GraphQL API.

## Stack
- Python 3.12
- `requests` — HTTP client
- `python-dotenv` — baca file `.env`

## Struktur File
```
main.py          # Script utama
setup.sh         # Setup otomatis (install deps + isi .env)
requirements.txt # Dependensi Python
.env.example     # Template konfigurasi
.env             # Konfigurasi aktif (JANGAN di-commit ke git)
```

## Cara Menjalankan

### Di Replit
1. Tambahkan secret `STAKE_API_TOKEN` di Replit Secrets
2. Jalankan: `python3 main.py`

### Di VPS (Ubuntu/Debian)
```bash
git clone <repo-url>
cd <folder>
bash setup.sh        # install deps + isi .env interaktif
source venv/bin/activate
python3 main.py
```

#### Background process (VPS)
```bash
source venv/bin/activate
nohup python3 main.py > plinko.log 2>&1 &
echo "PID: $!"

# Lihat log
tail -f plinko.log

# Stop
kill $(pgrep -f 'python3 main.py')
```

## Konfigurasi

| Variabel | Default | Keterangan |
|---|---|---|
| `STAKE_API_TOKEN` | — | **Wajib.** Token dari header `x-access-token` |
| `RISK` | `LOW` | `LOW` / `MEDIUM` / `HIGH` |
| `ROWS` | `8` | 8–16 |
| `BET_AMOUNT` | `500` | Nominal bet per round |
| `CURRENCY` | `IDR` | Kode mata uang |
| `BASE_DELAY_MS` | `200` | Jeda antar bet (ms) |
| `STOP_LOSS` | `10000` | Berhenti jika saldo ≤ nilai ini |
| `WAGER_TARGET` | `0` | Berhenti setelah total wager ini (0 = unlimited) |
| `MAX_CONSECUTIVE_ERRORS` | `5` | Berhenti setelah N error berturut-turut |
| `MAX_RATE_LIMIT_RETRIES` | `10` | Maks retry saat kena rate limit 429 |

## Cara Dapat Token
1. Buka [Stake.com](https://stake.com) dan login
2. Tekan `F12` → tab **Network**
3. Klik request apa saja ke `_api/graphql`
4. Buka **Request Headers** → salin nilai `x-access-token`

## User Preferences
- Bahasa komentar kode: Indonesia
- Target deploy: VPS (setup.sh) + Replit (untuk testing)
