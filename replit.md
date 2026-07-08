# Plinko Auto-Bet — Stake.com

Bot Python untuk melakukan auto-bet pada game Plinko di Stake.com via GraphQL API.

## Stack
- Python 3.12
- `requests` — HTTP client
- `python-dotenv` — baca file `.env`

## Struktur File
```
main.py             # Script utama
setup.sh            # Setup otomatis (install deps + isi .env)
requirements.txt    # Dependensi Python
config_profit.env   # Preset mode Profit (FLAT, bet 50–100, RISK=HIGH, ROWS via menu)
config_wager.env    # Preset mode Wager (Martingale 2-level, bet 500/1000, RISK=HIGH)
.env.example        # Referensi semua variabel yang tersedia
.env                # Token aktif — JANGAN di-commit ke git (dibuat oleh setup.sh)
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
python3 main.py      # menu interaktif: pilih mode + jumlah pin
```

#### Langsung tanpa menu (berguna untuk scripting)
```bash
python3 main.py profit --rows 14   # mode profit, 14 pin
python3 main.py profit --rows 16   # mode profit, 16 pin
python3 main.py wager              # mode wager
```

#### Background process (VPS) — WAJIB sertakan mode
```bash
# Mode profit 14 pin
nohup python3 main.py profit --rows 14 > plinko.log 2>&1 &
echo "PID: $!"

# Mode wager
nohup python3 main.py wager > plinko.log 2>&1 &
echo "PID: $!"

# Lihat log
tail -f plinko.log

# Stop
kill $(pgrep -f 'python3 main.py')
```

## Konfigurasi

Nilai berikut adalah default bawaan kode. Preset `config_profit.env` / `config_wager.env`
menimpa nilai ini; `.env` menimpa preset; shell env / Replit Secrets menimpa segalanya.

### Game
| Variabel | Default | Keterangan |
|---|---|---|
| `STAKE_API_TOKEN` | — | **Wajib.** Token dari header `x-access-token` |
| `RISK` | `LOW` | `LOW` / `MEDIUM` / `HIGH` |
| `ROWS` | `8` | Jumlah pin: 8–16 |
| `CURRENCY` | `IDR` | Kode mata uang Stake |

### Bet
| Variabel | Default | Keterangan |
|---|---|---|
| `BET_AMOUNT` | `500` | Bet tetap per round (diabaikan jika MIN/MAX diisi) |
| `BET_AMOUNT_MIN` | `0` | Batas bawah bet acak per siklus (0 = nonaktif) |
| `BET_AMOUNT_MAX` | `0` | Batas atas bet acak per siklus (0 = nonaktif) |

### Strategi
| Variabel | Default | Keterangan |
|---|---|---|
| `STRATEGY` | `FLAT` | `FLAT` / `ANTI_MARTINGALE` / `MARTINGALE` |
| `BET_MULTIPLIER` | `2` | Pengali bet (menang untuk Anti-M, kalah untuk Martingale) |
| `WIN_STREAK_CAP` | `3` | [Anti-M] Maks lipat berturut sebelum reset |
| `LOSS_STREAK_CAP` | `0` | [Martingale] Maks kalah berturut sebelum cut-loss (0 = tidak dibatas) |
| `MAX_BET` | `0` | Batas atas nominal bet per putaran (0 = tidak dibatas) |

### Timing
| Variabel | Default | Keterangan |
|---|---|---|
| `BASE_DELAY_MS` | `200` | Jeda tetap antar bet ms (diabaikan jika MIN/MAX diisi) |
| `BASE_DELAY_MIN_MS` | `0` | Batas bawah delay acak (ms, 0 = nonaktif) |
| `BASE_DELAY_MAX_MS` | `0` | Batas atas delay acak (ms, 0 = nonaktif) |

### Stop Conditions
| Variabel | Default | Keterangan |
|---|---|---|
| `STOP_LOSS` | `10000` | Berhenti jika **saldo absolut** ≤ nilai ini (0 = nonaktif) |
| `MAX_LOSS` | `0` | Berhenti jika **rugi relatif** ≥ nilai ini dari modal awal (0 = nonaktif) |
| `TAKE_PROFIT` | `0` | Berhenti jika profit bersih ≥ nilai ini (0 = nonaktif) |
| `TAKE_PROFIT_DELAY_SEC` | `30` | Countdown sebelum berhenti saat take profit (detik) |
| `JACKPOT_STOP_MULTIPLIER` | `0` | Berhenti langsung jika kena multiplier ini (0 = nonaktif) |
| `WAGER_TARGET` | `0` | Berhenti setelah total wager ini (0 = unlimited) |

### Safety & Log
| Variabel | Default | Keterangan |
|---|---|---|
| `MAX_CONSECUTIVE_ERRORS` | `5` | Berhenti setelah N error berturut-turut |
| `MAX_RATE_LIMIT_RETRIES` | `10` | Maks retry saat kena rate limit 429 |
| `LOG_FILE` | `auto` | `auto` = nama otomatis, `NONE` = nonaktif, atau nama file kustom |
| `LOG_MAX_LINES` | `1000` | Maks baris data di CSV; lebih lama otomatis dipangkas |

## Cara Dapat Token
1. Buka [Stake.com](https://stake.com) dan login
2. Tekan `F12` → tab **Network**
3. Klik request apa saja ke `_api/graphql`
4. Buka **Request Headers** → salin nilai `x-access-token`

## User Preferences
- Bahasa komentar kode: Indonesia
- Target deploy: VPS (setup.sh) + Replit (untuk testing)
