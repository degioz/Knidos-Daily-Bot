#!/usr/bin/env python3
"""
╔══════════════════════════════════════╗
║    Knidos Daily Bot By DEGIO         ║
║  Daily check-in + Game at 08:00 MMT  ║
╚══════════════════════════════════════╝

keys.txt  — one private key per line
proxy.txt — one proxy per line, paired with keys.txt (optional)

Game Flow (per game key):
  1. POST /api/games/session   -> session_token
  2. POST /api/games/progress  x 2
  3. POST /api/games/complete  -> reward

Usage:
  python3 knidos_bot.py
"""

import os
import sys
import time
import datetime
import requests
from eth_account import Account
from eth_account.messages import encode_defunct

# ── ANSI Colors ───────────────────────────────────────────────
RESET   = "\033[0m"
CYAN    = "\033[96m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
WHITE   = "\033[97m"
DIM     = "\033[2m"
BOLD    = "\033[1m"

# ── Config ────────────────────────────────────────────────────
BASE_URL      = "https://testnet.knidos.xyz"
KEYS_FILE     = "keys.txt"
PROXY_FILE    = "proxy.txt"       # optional — runs direct if missing
DELAY_SEC     = 2
INTERVAL_HOURS = 24               # repeat every 24 hours from start

# ── Game Config ───────────────────────────────────────────────
GAME_ENABLED        = True
GAME_KEYS           = ["game_1"]  # add more keys: ["game_1", "game_2"]
GAME_PROGRESS_CALLS = 3           # number of progress calls per session
GAME_PROGRESS_DELAY = 5.0         # seconds between progress calls

# ── Browser Headers ───────────────────────────────────────────
HEADERS = {
    "accept":             "*/*",
    "accept-language":    "en-US,en;q=0.9",
    "origin":             BASE_URL,
    "priority":           "u=1, i",
    "sec-ch-ua":          '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile":   "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest":     "empty",
    "sec-fetch-mode":     "cors",
    "sec-fetch-site":     "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "content-type": "application/json",
}


# ════════════════════════════════════════════════════════════
#   UI Helpers
# ════════════════════════════════════════════════════════════

def fmt_addr(address: str) -> str:
    """0xFB31...1c2b format"""
    return f"0x{address[2:6]}...{address[-4:]}"


def print_header(accounts: int, proxies: int):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    proxy_display = str(proxies) if proxies > 0 else "none"
    print()
    print(f"{'Start':<10}{CYAN}{now}{RESET}")
    print(f"{'Accounts':<10}{WHITE}{accounts}{RESET}  |  {'Proxies'} {CYAN}{proxy_display}{RESET}")
    print()


def print_wallet_header(index: int, address: str):
    addr = fmt_addr(address)
    line = "─" * (46 - len(str(index)) - len(addr))
    print(f"{CYAN}{index}. {addr} {line}{RESET}")


def print_status(label: str, ok: bool, detail: str = ""):
    status = f"{GREEN}Success{RESET}" if ok else f"{RED}Fail{RESET}"
    extra  = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {WHITE}{label:<8}{RESET}: {status}{extra}")


def print_status_already(label: str):
    print(f"  {WHITE}{label:<8}{RESET}: {YELLOW}Already Done{RESET}")


def print_status_reward(label: str, reward_str: str = ""):
    print(f"  {WHITE}{label:<8}{RESET}: {GREEN}Success{RESET}")


def print_footer(ok: int, already: int, fail: int, game_ok: int = 0, game_already: int = 0, game_fail: int = 0):
    print()
    parts = f"{GREEN}OK {ok}{RESET}  |  "
    if already:
        parts += f"{YELLOW}Already {already}{RESET}  |  "
    parts += f"{RED}Fail {fail}{RESET}"
    if GAME_ENABLED:
        parts += f"  |  Game {GREEN}{game_ok}{RESET}"
        if game_already:
            parts += f"/{YELLOW}{game_already}{RESET}"
        parts += f"/{RED}{game_fail}{RESET}"
    print(f"{'Done':<8}{parts}")


def sleep_with_countdown(target: datetime.datetime):
    """
    Next run: 2026-04-19 08:00:00
    Sleeping 17h 52m .
    """
    dots   = [".", " "]
    toggle = 0
    next_str = target.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{CYAN}Next run: {next_str}{RESET}")
    print(f"{WHITE}Sleeping --h --m {GREEN}.{RESET}  ")
    while True:
        now  = datetime.datetime.now()
        diff = (target - now).total_seconds()
        if diff <= 0:
            break
        h   = int(diff // 3600)
        m   = int((diff % 3600) // 60)
        dot = dots[toggle % 2]
        toggle += 1
        sys.stdout.write("\033[1A\r")
        sys.stdout.write(
            f"{WHITE}Sleeping {h}h {m}m {GREEN}{dot}{RESET}   \n"
        )
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\n")
    sys.stdout.flush()


# ════════════════════════════════════════════════════════════
#   File Loaders
# ════════════════════════════════════════════════════════════

def load_lines(filepath: str) -> list:
    """Returns empty list if file is missing — not an error."""
    if not os.path.exists(filepath):
        return []
    lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


def parse_proxy(proxy_str: str) -> dict:
    """Returns {} (direct connection) when proxy_str is empty."""
    if not proxy_str:
        return {}
    if proxy_str.startswith("socks5://"):
        proxy_str = proxy_str.replace("socks5://", "socks5h://", 1)
    return {"http": proxy_str, "https": proxy_str}


# ════════════════════════════════════════════════════════════
#   Core Bot Logic
# ════════════════════════════════════════════════════════════

def get_address(private_key: str) -> str:
    return Account.from_key(private_key).address


def get_challenge(session: requests.Session, address: str) -> dict:
    resp = session.post(
        f"{BASE_URL}/api/wallet/challenge",
        json={"address": address, "challengeType": "wallet_login"},
        headers={**HEADERS, "referer": f"{BASE_URL}/login"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise Exception(f"Challenge error: {data.get('error')}")
    return data["challenge"]


def sign_message(private_key: str, message: str) -> str:
    """Ethereum personal_sign — same as MetaMask signMessage (0x-prefixed)"""
    account = Account.from_key(private_key)
    msg = encode_defunct(text=message)
    raw = account.sign_message(msg).signature.hex()
    return raw if raw.startswith("0x") else f"0x{raw}"


def wallet_login(session: requests.Session, address: str, sig: str, nonce: str):
    resp = session.post(
        f"{BASE_URL}/api/session/login/wallet",
        json={"wallet": address, "signature": sig},
        headers={**HEADERS, "referer": f"{BASE_URL}/login"},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        error = data.get("error", "unknown")
        msg   = data.get("message", "")
        if error in ("wallet_not_found", "user_not_found", "account_not_found",
                     "invalid_credentials"):
            raise Exception("not registered on Knidos testnet")
        if error in ("wallet_signature_invalid", "invalid_signature"):
            raise Exception("signature invalid — wrong key")
        if error == "wallet_challenge_required":
            raise Exception("challenge expired — retry")
        raise Exception(f"{error}: {msg}")


def do_checkin(session: requests.Session) -> dict:
    resp = session.post(
        f"{BASE_URL}/api/checkin",
        data=b"",
        headers={
            **HEADERS,
            "referer":        f"{BASE_URL}/dashboard?menu=referral",
            "content-length": "0",
        },
        timeout=30,
    )
    return resp.json()


# ════════════════════════════════════════════════════════════
#   Game Functions
# ════════════════════════════════════════════════════════════

GAME_REFERER_TPL = f"{BASE_URL}/dashboard?menu=games&game={{game_key}}"

ALREADY_ERRORS = {
    "already_checked_in",
    "checkin_already_completed_today",
    "already_claimed",
    "duplicate",
    "already_done",
    "already_played",
    "game_already_played",
    "game_already_completed",
    "game_already_completed_today",
    "already_completed",
    "session_already_completed",
    "game_limit_reached",
}


class AlreadyDoneError(Exception):
    pass


def game_start_session(session: requests.Session, game_key: str) -> str:
    """POST /api/games/session -> returns session_token"""
    referer = GAME_REFERER_TPL.format(game_key=game_key)
    resp = session.post(
        f"{BASE_URL}/api/games/session",
        json={"game_key": game_key},
        headers={**HEADERS, "referer": referer},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        error = data.get("error", "unknown")
        if error in ALREADY_ERRORS:
            raise AlreadyDoneError(error)
        raise Exception(f"session error: {error} — {data.get('message', '')}")
    # handle varying key names in response
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    token = (data.get("session_token") or data.get("token") or
             inner.get("session_token") or inner.get("token"))
    if not token:
        raise Exception(f"session_token not found in response: {data}")
    return token


def game_send_progress(session: requests.Session, game_key: str, session_token: str):
    """POST /api/games/progress"""
    referer = GAME_REFERER_TPL.format(game_key=game_key)
    resp = session.post(
        f"{BASE_URL}/api/games/progress",
        json={"game_key": game_key, "session_token": session_token},
        headers={**HEADERS, "referer": referer},
        timeout=30,
    )
    return resp.json()


def game_complete(session: requests.Session, game_key: str, session_token: str) -> dict:
    """POST /api/games/complete -> reward data"""
    referer = GAME_REFERER_TPL.format(game_key=game_key)
    resp = session.post(
        f"{BASE_URL}/api/games/complete",
        json={"game_key": game_key, "session_token": session_token},
        headers={**HEADERS, "referer": referer},
        timeout=30,
    )
    return resp.json()


def extract_reward(data: dict) -> str:
    """Pull reward/AP/points value out of a response dict."""
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    val = (data.get("reward") or data.get("ap") or data.get("points") or
           data.get("score") or data.get("ap_earned") or
           inner.get("reward") or inner.get("ap") or inner.get("points") or
           inner.get("ap_earned") or inner.get("score"))
    return f"+{val} AP" if val else ""


def do_game_key(session: requests.Session, game_key: str) -> tuple:
    """Run one game key. Returns (ok, already, reward_str, error_hint)."""
    try:
        session_token = game_start_session(session, game_key)
    except AlreadyDoneError:
        return False, True, "", ""
    except Exception as e:
        return False, False, "", str(e)[:50]

    for _ in range(GAME_PROGRESS_CALLS):
        try:
            game_send_progress(session, game_key, session_token)
        except Exception:
            pass
        time.sleep(GAME_PROGRESS_DELAY)

    # wait before completing so server can verify progress
    time.sleep(3.0)

    try:
        result = game_complete(session, game_key, session_token)
        if result.get("ok"):
            return True, False, extract_reward(result), ""
        error = result.get("error", "")
        if error in ALREADY_ERRORS:
            return False, True, "", ""
        return False, False, "", result.get("message", error)[:50]
    except Exception as e:
        return False, False, "", str(e)[:50]


# ════════════════════════════════════════════════════════════
#   Per-wallet Runner
# ════════════════════════════════════════════════════════════

def run_wallet(index: int, private_key: str, proxy_str: str):
    """Returns (checkin_new, checkin_already, login_fail, game_ok_count, game_already_count)"""
    try:
        address = get_address(private_key)
    except Exception:
        print_wallet_header(index, "0x????...????")
        print_status("Login",    False, "invalid key")
        print_status("Check-in", False, "skipped")
        if GAME_ENABLED:
            for gk in GAME_KEYS:
                print_status(f"Game({gk})", False, "skipped")
        print()
        return False, False, True, 0, 0

    print_wallet_header(index, address)

    proxies = parse_proxy(proxy_str)
    session = requests.Session()
    if proxies:
        session.proxies.update(proxies)

    # ── Login ─────────────────────────────────────────────────
    try:
        challenge = get_challenge(session, address)
        sig       = sign_message(private_key, challenge["message"])
        wallet_login(session, address, sig, challenge["nonce"])
        print_status("Login", True)

    except Exception as e:
        err = str(e)
        if "not registered" in err:
            hint = "not registered"
        elif "invalid_signature" in err or "wrong key" in err:
            hint = "signature invalid"
        elif "challenge_expired" in err or "expired" in err:
            hint = "challenge expired"
        elif "ProxyError" in type(e).__name__ or "proxy" in err.lower():
            hint = "proxy error"
        elif "Timeout" in type(e).__name__:
            hint = "timeout"
        else:
            hint = err[:40]
        print_status("Login",    False, hint)
        print_status("Check-in", False, "skipped")
        if GAME_ENABLED:
            for gk in GAME_KEYS:
                print_status(f"Game({gk})", False, "skipped")
        print()
        session.close()
        return False, False, True, 0, 0

    # ── Check-in ──────────────────────────────────────────────
    checkin_new     = False
    checkin_already = False
    try:
        result = do_checkin(session)
        if result.get("ok"):
            checkin_new = True
            print_status("Check-in", True)
        else:
            error = result.get("error", "")
            if error in ALREADY_ERRORS:
                checkin_already = True
                print_status_already("Check-in")
            else:
                hint = result.get("message", error)[:40]
                print_status("Check-in", False, hint)
    except Exception as e:
        print_status("Check-in", False, str(e)[:40])

    # ── Daily Games ───────────────────────────────────────────
    game_ok_count      = 0
    game_already_count = 0

    if GAME_ENABLED:
        for game_key in GAME_KEYS:
            ok, already, reward_str, hint = do_game_key(session, game_key)
            if ok:
                game_ok_count += 1
                print_status_reward("Game")
            elif already:
                game_already_count += 1
                print_status_already("Game")
            else:
                print_status("Game", False, hint)

    print()
    session.close()
    return checkin_new, checkin_already, False, game_ok_count, game_already_count


# ════════════════════════════════════════════════════════════
#   Scheduler
# ════════════════════════════════════════════════════════════

def next_run_time() -> datetime.datetime:
    return datetime.datetime.now() + datetime.timedelta(hours=INTERVAL_HOURS)


# ════════════════════════════════════════════════════════════
#   Daily Run
# ════════════════════════════════════════════════════════════

def run_all():
    keys    = load_lines(KEYS_FILE)
    proxies = load_lines(PROXY_FILE)

    if not keys:
        print(f"{RED}keys.txt not found or empty{RESET}")
        print(f"   Format: one private key per line")
        sys.exit(1)

    print_header(len(keys), len(proxies))

    ok_count           = 0
    already_count      = 0
    fail_count         = 0
    game_ok_total      = 0
    game_already_total = 0
    game_fail_total    = 0

    for i, key in enumerate(keys, 1):
        proxy = proxies[i - 1] if i <= len(proxies) else ""
        new, already, failed, game_ok, game_already = run_wallet(
            i, key.strip(), proxy.strip()
        )

        if new:
            ok_count += 1
        elif already:
            already_count += 1
        else:
            fail_count += 1

        if GAME_ENABLED:
            game_ok_total      += game_ok
            game_already_total += game_already
            game_fail_total    += (len(GAME_KEYS) - game_ok - game_already)

        if i < len(keys):
            time.sleep(DELAY_SEC)

    print_footer(ok_count, already_count, fail_count,
                 game_ok_total, game_already_total, game_fail_total)
    return next_run_time()


# ════════════════════════════════════════════════════════════
#   Main — runs immediately, then repeats every 24 hours
# ════════════════════════════════════════════════════════════

def main():
    w = 46
    print(f"\n{CYAN}{'═'*w}{RESET}")
    print(f"{CYAN}{'Knidos Daily Bot By DEGIO':^{w}}{RESET}")
    print(f"{CYAN}{'═'*w}{RESET}")

    while True:
        next_run = run_all()
        sleep_with_countdown(next_run)


if __name__ == "__main__":
    main()
