# Knidos Daily Bot 🤖

Automated daily check-in and game bot for [Knidos Testnet](https://testnet.knidos.xyz), built by **DEGIO**.

Runs every 24 hours — performs wallet login, daily check-in, and game sessions automatically.

---

## Features

- ✅ Daily check-in automation
- ✅ Game session automation
- ✅ Multi-wallet support
- ✅ Optional proxy support
- ✅ Loops every 24 hours automatically

---

## Requirements

- Python 3.8+
- pip packages (see `requirements.txt`)

---

## Installation

```bash
git clone https://github.com/degioz/knidos-daily-bot.git
cd knidos-daily-bot
pip install -r requirements.txt
```

Or use the setup script:

```bash
chmod +x setup.sh
./setup.sh
```

---

## Configuration

### 1. `keys.txt` — Private Keys (required)

One Ethereum private key per line:

```
0xabc123...
0xdef456...
```

> ⚠️ **Never share your private keys or commit `keys.txt` to GitHub.** It is already in `.gitignore`.

### 2. `proxy.txt` — Proxies (optional)

One proxy per line, paired with `keys.txt` by line number:

```
http://user:pass@host:port
socks5://user:pass@host:port
```

Leave the file empty or omit it entirely to run without proxies.

---

## Usage

```bash
python3 bot.py
```

```bash
python bot.py
```

The bot will:
1. Run immediately on start
2. Show a live countdown timer
3. Repeat every 24 hours automatically

---

## Running in Background

**Linux/macOS (screen):**
```bash
screen -S knidos
python3 bot.py
# Detach: Ctrl+A then D
# Reattach: screen -r knidos
```

**Linux (nohup):**
```bash
nohup python3 bot.py > bot.log 2>&1 &
```

---

## File Structure

```
knidos-daily-bot/
├── bot.py          # Main bot script
├── keys.txt        # Private keys (not committed)
├── proxy.txt       # Proxies (not committed, optional)
├── requirements.txt
├── setup.sh
└── README.md
```

---

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The author is not responsible for any loss of funds or account bans. Always keep your private keys safe.

---

## License

MIT License
