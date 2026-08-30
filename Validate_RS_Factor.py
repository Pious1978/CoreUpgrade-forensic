"""
Validate_RS_Factor.py

Real, rigorous validation of our actual RS percentile factor - adapted
from Alpha1's real Factor_Validation.py methodology (Information
Coefficient + decile returns, the standard "does this factor predict
anything" quant research test).

Our live daily_snapshot table only has 3 real dates so far - nowhere
near enough to pair against forward returns. Rather than wait weeks/
months for that to accumulate, this retroactively reconstructs
rs_percentile at many past dates using our own already-backfilled 1.5-2
years of real price history in parquet_cache - the same technique
Alpha1's own backfill_historical_snapshots.py used.

Critically, this reconstructs our EXACT, real, current formula
(RelativeStrengthEngine.py's rs_raw_return = 250-trading-day return,
then cross-sectionally ranked into a percentile) - not a hypothetical
improved version. We're testing what we actually have.
"""

import pandas as pd
import numpy as np
import os
from scipy.stats import spearmanr

from core.config import PARQUET_CACHE_DIR, UNIVERSE_CSV_PATH, MIN_TRADING_DAYS_RS

LOOKBACK_DAYS = 250   # matches RelativeStrengthEngine.py's real formula exactly
STEP_DAYS = 10        # spacing between "as-of" test dates - avoids near-duplicate,
                       # highly overlapping windows while still getting good coverage
HORIZONS = {
    "4-week (20 trading days)": 20,
    "12-week (60 trading days)": 60,
    "26-week (130 trading days)": 130,
}


def load_all_price_series():
    """Loads every stock's real close-price series once, into memory -
    avoids repeated file I/O across many as-of dates and horizons."""

    print("[*] Loading real price history from parquet_cache...")

    series_map = {}

    for fname in os.listdir(PARQUET_CACHE_DIR):
        if not fname.endswith(".parquet") or "NIFTYBEES" in fname or "^NSEI" in fname:
            continue

        symbol = fname.replace(".parquet", "")
        path = os.path.join(PARQUET_CACHE_DIR, fname)

        try:
            df = pd.read_parquet(path)
            df.columns = [str(c).lower() for c in df.columns]
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            # Only drop rows missing the price data this needs - a
            # blanket dropna() would also drop backfilled rows missing
            # delivery_qty/delivery_pct (intentionally NULL for
            # Yahoo-sourced history). Same real bug found and fixed
            # across several scanners tonight.
            df = df.dropna(subset=["close"])

            if len(df) < LOOKBACK_DAYS + max(HORIZONS.values()):
                continue

            series_map[symbol] = df["close"]

        except Exception:
            continue

    print(f"[+] Loaded {len(series_map)} stocks with genuinely sufficient real history.")
    return series_map


def build_factor_forward_return_pairs(series_map):
    """
    For each stock, walks through many real historical "as-of" dates,
    reconstructing rs_raw_return exactly as RelativeStrengthEngine.py
    computes it live, then pairs it with the REAL forward return at
    each horizon. Cross-sectional ranking happens per as-of date,
    matching the real, live methodology (ranked against whichever
    stocks have valid data on that specific date).

    Real, important fix found during testing: spacing between as-of
    dates must scale with each horizon's own length, not stay fixed.
    With a short, fixed spacing and a long forward horizon, consecutive
    test windows overlap heavily (e.g. 92% overlap at 130 days forward
    with only 10-day spacing) - confirmed directly, pure noise data
    produced a spuriously "significant" p-value at the 26-week horizon
    before this fix, because the statistical test assumes independent
    observations that heavily-overlapping windows genuinely aren't.
    Spacing each horizon's test dates by its own forward length keeps
    windows non-overlapping and the significance test honest.
    """

    all_lengths = [len(s) for s in series_map.values()]
    max_len = max(all_lengths)

    pairs = {h_name: [] for h_name in HORIZONS}

    for h_name, h_days in HORIZONS.items():

        # Non-overlapping spacing for this specific horizon
        usable_range = list(range(LOOKBACK_DAYS, max_len - h_days, h_days))

        print(f"[*] {h_name}: testing {len(usable_range)} genuinely "
              f"non-overlapping historical as-of points...")

        for idx in usable_range:

            raw_returns_this_date = {}

            for symbol, close in series_map.items():
                if idx >= len(close):
                    continue

                price_now = float(close.iloc[idx])
                price_250_ago = float(close.iloc[idx - LOOKBACK_DAYS])

                if price_250_ago <= 0:
                    continue

                raw_returns_this_date[symbol] = (price_now - price_250_ago) / price_250_ago

            if len(raw_returns_this_date) < 30:
                continue

            # Real, exact cross-sectional ranking - same as RelativeStrengthEngine.py
            rs_series = pd.Series(raw_returns_this_date)
            percentiles = rs_series.rank(method="average", pct=True) * 100.0

            for symbol, pct in percentiles.items():
                close = series_map[symbol]
                future_idx = idx + h_days

                if future_idx >= len(close):
                    continue

                price_now = float(close.iloc[idx])
                price_future = float(close.iloc[future_idx])

                if price_now <= 0:
                    continue

                fwd_return_pct = ((price_future - price_now) / price_now) * 100

                pairs[h_name].append({
                    "symbol": symbol,
                    "factor": pct,
                    "forward_return_pct": fwd_return_pct,
                })

    return {h_name: pd.DataFrame(rows) for h_name, rows in pairs.items()}


def information_coefficient(pair_df):
    if len(pair_df) < 30:
        return {"ic": None, "p_value": None, "n": len(pair_df),
                "note": "Too few pairs to compute a meaningful IC."}
    ic, p_value = spearmanr(pair_df["factor"], pair_df["forward_return_pct"])
    return {"ic": round(ic, 4), "p_value": round(p_value, 6), "n": len(pair_df)}


def decile_returns(pair_df):
    df = pair_df.copy()
    try:
        df["decile"] = pd.qcut(df["factor"], 10, labels=False, duplicates="drop") + 1
    except ValueError:
        df["decile"] = pd.qcut(df["factor"], 5, labels=False, duplicates="drop") + 1

    summary = df.groupby("decile").agg(
        avg_forward_return_pct=("forward_return_pct", "mean"),
        median_forward_return_pct=("forward_return_pct", "median"),
        win_rate_pct=("forward_return_pct", lambda x: (x > 0).mean() * 100),
        n=("forward_return_pct", "count"),
    ).round(2)
    return summary


def run():

    print()
    print("=" * 70)
    print("REAL FACTOR VALIDATION - RS PERCENTILE")
    print("=" * 70)
    print("Testing our own, actual, live rs_percentile formula against")
    print("real historical forward returns - not a hypothetical or")
    print("improved version, exactly what RelativeStrengthEngine.py")
    print("computes today.")
    print()

    series_map = load_all_price_series()

    if len(series_map) < 30:
        print("[-] Not enough stocks with sufficient real history to run this validation yet.")
        return

    pairs_by_horizon = build_factor_forward_return_pairs(series_map)

    for h_name, pair_df in pairs_by_horizon.items():

        print(f"\n{'='*60}")
        print(f"HORIZON: {h_name}")
        print(f"{'='*60}")

        if pair_df.empty:
            print("[-] Not enough real history for this horizon - skipping.")
            continue

        ic_result = information_coefficient(pair_df)
        print(f"Information Coefficient: {ic_result}")

        if ic_result["ic"] is not None:
            abs_ic = abs(ic_result["ic"])
            if abs_ic < 0.02:
                verdict = "No real signal - factor looks close to noise at this horizon."
            elif abs_ic < 0.05:
                verdict = "Weak signal - worth tracking, not yet worth trading on alone."
            else:
                verdict = "Real signal - meaningfully predictive at this horizon."
            print(f"  -> {verdict}")

        print("\nDecile returns (Decile 10 = highest rs_percentile):")
        print(decile_returns(pair_df).to_string())

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run()