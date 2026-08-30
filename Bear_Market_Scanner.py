"""
Bear_Market_Scanner.py

Genuine value/mean-reversion scanner, methodologically adapted from
Alpha1's real, working Bear_Market_Scanner.py (confirmed as legitimate,
tested code during tonight's investigation - not the dead
execution_candidates architecture found elsewhere in this repo).

Fundamentally different in philosophy from Consolidation_Scanner.py,
Hybrid_Alpha_Scanner.py, Emerging_Leader_Scanner.py, and Cup_and_Handle.py,
which all look for bullish continuation setups (a stock about to break
out of a tight base). This looks for stocks that have fallen
significantly (25-80% from their 52-week high) but show real signs of
stabilizing - genuine relative strength against the index despite the
fall (an anti-value-trap filter), oversold RSI, and price holding at a
meaningful Fibonacci retracement level.

Uses our own backfilled parquet_cache (1.5-2 years of real history for
most of the universe) instead of live yfinance calls - no live network
dependency, unlike Alpha1's original version.

Runs as a fully automated pipeline stage (no interactive input) -
activated by Pipeline_DAG_Executor.py only when the real, current market
regime (from Market_Regime_Engine.py) is BEAR or DISTRIBUTION, since
these deep-pullback value setups aren't relevant in a genuine uptrend.
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime

from core.config import PARQUET_CACHE_DIR, DB_PATH, UNIVERSE_CSV_PATH, NIFTY_BENCHMARK_SYMBOL, BASE_DIR

MIN_PRICE = 20
MIN_VOLUME = 200000
MIN_PULLBACK = 25
MAX_PULLBACK = 80
RSI_OVERSOLD = 35
RSI_ACCUMULATION = 50
MIN_RR = 2.0
TARGET_RECOVERY = 0.50
MIN_RS_ALPHA = -0.10


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def nearest_fib(price, high, low):
    diff = high - low
    fibs = {
        "23.6%": high - diff * 0.236,
        "38.2%": high - diff * 0.382,
        "50.0%": high - diff * 0.500,
        "61.8%": high - diff * 0.618,
        "78.6%": high - diff * 0.786,
    }
    return min(fibs.items(), key=lambda x: abs(price - x[1]))[0]


def load_universe():
    """Reuses the same NSE_EQ.csv universe file every other scanner in
    this pipeline already relies on, for consistency."""

    try:
        df = pd.read_csv(UNIVERSE_CSV_PATH)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            print("[-] SYMBOL column missing from universe file.")
            return []

        symbol_col = df.columns[cols.index("SYMBOL")]

        symbols = (
            df[symbol_col]
            .dropna()
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )

        return sorted(set(s for s in symbols if len(s) >= 2))

    except Exception as e:
        print(f"[-] Error loading universe: {e}")
        return []


def analyze_stock(ticker, nifty_df):

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # Only drop rows missing the price data this calculation needs -
        # a blanket dropna() would also drop every backfilled row missing
        # delivery_qty/delivery_pct (intentionally NULL for Yahoo-sourced
        # history), collapsing usable history back to the raw bhav-copy
        # days alone. Same real bug found and fixed in
        # Market_Regime_Engine.py earlier tonight.
        df = df.dropna(subset=["close", "high", "low"])

        if len(df) < 200:
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        current_price = float(close.iloc[-1])

        if current_price < MIN_PRICE:
            return None

        avg_volume = float(volume.tail(20).mean())
        if avg_volume < MIN_VOLUME:
            return None

        common_dates = df.index.intersection(nifty_df.index)
        lookback_idx = min(126, len(common_dates) - 1)

        if lookback_idx < 40:
            return None

        stock_hist = float(close.loc[common_dates[-lookback_idx]])
        nifty_hist = float(nifty_df["close"].loc[common_dates[-lookback_idx]])

        stock_perf = (current_price - stock_hist) / stock_hist
        nifty_perf = (float(nifty_df["close"].iloc[-1]) - nifty_hist) / nifty_hist
        rs_alpha = stock_perf - nifty_perf

        if rs_alpha < MIN_RS_ALPHA:
            return None

        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])

        if np.isnan(sma50) or np.isnan(sma200):
            return None

        high_52w = float(high.tail(252).max())
        low_52w = float(low.tail(252).min())

        if high_52w <= low_52w:
            return None

        pullback_pct = ((high_52w - current_price) / high_52w) * 100

        if not (MIN_PULLBACK <= pullback_pct <= MAX_PULLBACK):
            return None

        rsi_series = calculate_rsi(close)
        if rsi_series.isna().all():
            return None
        rsi = float(rsi_series.iloc[-1])

        fib = nearest_fib(current_price, high_52w, low_52w)

        entry = round(current_price, 2)
        recent_low = float(low.tail(30).min())
        sl = round(recent_low * 0.97, 2)
        risk = entry - sl

        if risk <= 0:
            return None

        target1 = round(current_price + (high_52w - current_price) * TARGET_RECOVERY, 2)
        reward = target1 - entry
        rr = round(reward / risk, 2)

        if rr < MIN_RR:
            return None

        score = 0
        if pullback_pct >= 50: score += 2
        elif pullback_pct >= 35: score += 1

        if rsi <= RSI_OVERSOLD: score += 3
        elif rsi <= RSI_ACCUMULATION: score += 2
        elif rsi <= 70: score += 1

        if fib in ["78.6%", "61.8%"]: score += 2
        elif fib == "50.0%": score += 1

        if current_price > sma50: score += 1
        if current_price > sma200: score += 1

        if rs_alpha > 0.10: score += 2
        elif rs_alpha > 0: score += 1

        signal = "WATCH"
        if score >= 8: signal = "DEEP VALUE"
        elif score >= 6: signal = "VALUE BUY"
        elif score >= 5: signal = "ACCUMULATE"

        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "pullback_pct": round(pullback_pct, 2),
            "rsi": round(rsi, 1),
            "rs_alpha_pct": round(rs_alpha * 100, 2),
            "nearest_fib": fib,
            "entry": entry,
            "stop_loss": sl,
            "target_1": target1,
            "rr": rr,
            "score": score,
            "signal": signal,
        }

    except Exception:
        return None


def run():

    print()
    print("=" * 70)
    print("BEAR MARKET VALUE SCANNER")
    print("=" * 70)

    nifty_path = os.path.join(PARQUET_CACHE_DIR, f"{NIFTY_BENCHMARK_SYMBOL}.parquet")

    if not os.path.exists(nifty_path):
        print(f"[-] Benchmark file not found: {nifty_path}")
        return

    nifty_df = pd.read_parquet(nifty_path)
    nifty_df.columns = [str(c).lower() for c in nifty_df.columns]
    nifty_df["date"] = pd.to_datetime(nifty_df["date"])
    nifty_df = nifty_df.set_index("date").sort_index()
    nifty_df = nifty_df.dropna(subset=["close"])

    symbols = load_universe()

    if not symbols:
        print("[-] No symbols loaded from universe file.")
        return

    print(f"[*] Scanning {len(symbols)} stocks for genuine deep-pullback value setups...")

    results = []

    for symbol in symbols:
        result = analyze_stock(symbol, nifty_df)
        if result:
            results.append(result)

    if not results:
        print("[+] No setups cleared the filters today.")
        return

    out = pd.DataFrame(results).sort_values(by=["score", "rr"], ascending=False)

    today = datetime.now().strftime("%Y-%m-%d")
    out["date"] = today

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS bear_market_candidates (
            ticker TEXT,
            price REAL,
            pullback_pct REAL,
            rsi REAL,
            rs_alpha_pct REAL,
            nearest_fib TEXT,
            entry REAL,
            stop_loss REAL,
            target_1 REAL,
            rr REAL,
            score INTEGER,
            signal TEXT,
            date TEXT,
            PRIMARY KEY (ticker, date)
        )
    """)

    conn.execute("DELETE FROM bear_market_candidates WHERE date = ?", (today,))
    out.to_sql("bear_market_candidates", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, "BEAR_MARKET_WATCHLIST.xlsx")
    out.to_excel(excel_path, index=False)

    deep_value = out[out["signal"] == "DEEP VALUE"]
    value_buy = out[out["signal"] == "VALUE BUY"]
    accumulate = out[out["signal"] == "ACCUMULATE"]
    watch = out[out["signal"] == "WATCH"]

    print()
    print(f"DEEP VALUE  : {len(deep_value)}")
    print(f"VALUE BUY   : {len(value_buy)}")
    print(f"ACCUMULATE  : {len(accumulate)}")
    print(f"WATCH       : {len(watch)}")
    print(f"TOTAL       : {len(out)}")
    print(f"[+] Written to bear_market_candidates and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()