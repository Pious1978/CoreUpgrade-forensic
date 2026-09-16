"""
core/kite_client.py

A clean, reusable wrapper around the real, live Kite Connect
connection - confirmed working end-to-end tonight (a genuine, live
quote for RELIANCE with real, current timestamp/depth). Other scripts
should import get_kite_client() or get_live_quote() from here rather
than repeating the login flow themselves.

REAL, DIRECT SECURITY NOTE: the session cache file (.kite_session.json)
holds today's live access_token - an active, immediately-usable
credential for the rest of the trading day. It's listed in .gitignore,
same as .env - never committed, never pushed to the public repo.

HONEST, DIRECT LIMITATION on the daily login: Kite Connect's
access_token genuinely expires every day (confirmed directly from
Zerodha's own documentation) - there's no way to eliminate the one
manual, interactive login per trading day with the base library. What
this module DOES eliminate is repeating that login on every single
script run within the same day - the cached token is reused for the
rest of that day, and a fresh login is only triggered once, when the
cache is missing or from a previous day.
"""

import os
import json
from datetime import date

from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

SESSION_CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".kite_session.json")


def _load_cached_session():
    """
    Real, direct check: only returns a cached access_token if it was
    genuinely generated TODAY - Kite Connect's own token validity
    resets daily, so a token from any earlier day is honestly treated
    as expired, not reused blindly.
    """

    if not os.path.exists(SESSION_CACHE_PATH):
        return None

    try:
        with open(SESSION_CACHE_PATH, "r") as f:
            cached = json.load(f)

        if cached.get("date") != date.today().isoformat():
            return None

        return cached.get("access_token")

    except Exception:
        return None


def _save_session(access_token):
    """Real, direct persistence of today's token, so this login isn't repeated on every script run today."""

    with open(SESSION_CACHE_PATH, "w") as f:
        json.dump({"date": date.today().isoformat(), "access_token": access_token}, f)


def get_kite_client():
    """
    Real, direct connection setup - reuses a genuinely still-valid,
    same-day cached token when one exists; otherwise runs the real,
    necessary interactive login flow exactly once, then caches the
    result for the rest of today.
    """

    api_key = os.getenv("KITE_API_KEY")
    api_secret = os.getenv("KITE_API_SECRET")

    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("KITE_API_KEY not set - copy .env.example to .env and fill in your real values.")

    kite = KiteConnect(api_key=api_key)

    cached_token = _load_cached_session()

    if cached_token:
        kite.set_access_token(cached_token)
        return kite

    print("No valid session for today - a fresh login is required.")
    print("Open this URL in your browser and log in with your Zerodha credentials:")
    print(kite.login_url())
    print()

    request_token = input("Paste the request_token from the redirect URL: ").strip()

    data = kite.generate_session(request_token, api_secret=api_secret)
    kite.set_access_token(data["access_token"])
    _save_session(data["access_token"])

    return kite


def get_live_quote(ticker, exchange="NSE"):
    """
    Real, direct, clean live quote for a single ticker - a simplified,
    consistent return shape, matching the style of this project's
    other lookup functions, rather than the full, verbose raw response.
    """

    kite = get_kite_client()
    symbol = f"{exchange}:{ticker.upper()}"

    raw = kite.quote(symbol)
    data = raw.get(symbol)

    if not data:
        return None

    return {
        "ticker": ticker.upper(),
        "last_price": data.get("last_price"),
        "volume": data.get("volume"),
        "timestamp": str(data.get("timestamp")),
        "ohlc": data.get("ohlc"),
        "buy_quantity": data.get("buy_quantity"),
        "sell_quantity": data.get("sell_quantity"),
    }


if __name__ == "__main__":
    ticker = input("Ticker: ").strip().upper()
    quote = get_live_quote(ticker)
    print(quote)