"""
SwingBacktest/Full_Backtest.py

#54F - Full swing-trading system backtest.

Wires together everything built so far:
- #54A (Historical_Data_Provider): point-in-time price data, no look-ahead
- #54B (Historical_Scanner_Reconstruction): real candidates at each date
- #54C (Historical_Regime_Reconstruction): real regime at each date
- #54D (Daily_Volume_Ratio): honest RVOL proxy
- #54E (Trade_Simulator): deterministic single-trade outcomes

Reuses the exact real formulas from the forensic mapping:
- Entry: trigger = pivot x 1.005, requires daily_volume_ratio >= 1.5
  (the honest proxy for live rvol >= 1.5)
- Stop: pivot - (1.5 x ATR14)
- Targets: Risk_Positioning_Engine.py's real dynamic R:R multipliers
- Sizing: risk_budget = capital x regime_multiplier x 0.5%, capped at
  20% concentration, MAX_POSITIONS=10, MAX_PER_SECTOR=3

HONEST SCOPE, carried forward from #54B: candidates only come from
Consolidation_Scanner.py (1 of 5 real discovery scanners), sampled
every 5 trading days by default. This is a real, if partial, first
answer - not the final word. Composite_Score isn't available at this
scope (that's Master_Terminal.py's multi-factor output, which needs
all 5 scanners reconstructed) - this uses each candidate's own
confidence score as the closest available proxy, honestly labeled as
such in the assumptions manifest below.

Writes every result alongside its own assumptions manifest - so six
months from now, "what exactly produced this number" has a real answer.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import sqlite3
import json
from datetime import datetime

from Historical_Data_Provider import PointInTimeMarketData
from Daily_Volume_Ratio import compute_daily_volume_ratio
from Trade_Simulator import simulate_trade
from Risk_Positioning_Engine import calculate_dynamic_rr_multipliers
from core.sector_map import get_sector

BACKTEST_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.db")

DEFAULT_ASSUMPTIONS = {
    "backtest_version": "1.0",
    "data": "Daily OHLCV, point-in-time truncated (#54A)",
    "signal_source": "Consolidation_Scanner.py only (1 of 5 real discovery scanners) - #54B first pass, honest partial scope",
    "candidate_sampling": "every 5 trading days",
    "rvol": "unavailable historically; replaced with daily_volume_ratio proxy (#54D), threshold >= 1.5",
    "regime": "historical reconstruction enabled (#54C), reuses Market_Regime_Engine.py's real logic",
    "composite_score_proxy": "candidate confidence score (Consolidation_Scanner.py's own 0-1 structural confidence) - not the full multi-factor Master_Terminal.py Composite_Score, which needs all 5 scanners",
    "look_ahead": "prohibited - enforced by #54A's PointInTimeMarketData",
    "survivorship": "universe reflects currently-listed stocks only; delisted names are invisible",
    "entry": "price >= pivot x 1.005 AND daily_volume_ratio >= 1.5, evaluated on the candidate's own discovery date",
    "stop": "pivot - (1.5 x ATR14)",
    "target": "Risk_Positioning_Engine.py's real dynamic R:R multipliers",
    "same_bar_policy": "STOP_FIRST (conservative default)",
    "slippage": "NOT MODELED - a real, honest limitation of this first pass",
    "brokerage": "NOT MODELED - a real, honest limitation of this first pass",
    "risk_per_trade_pct": 0.005,
    "max_positions": 10,
    "max_per_sector": 3,
    "concentration_cap_pct": 0.20,
}


def compute_atr14_point_in_time(price_history, period=14):
    """
    Real ATR formula, matching core/technical_indicators.py's exact
    live calculation - reimplemented here to accept a point-in-time
    truncated DataFrame directly, since the live function reads from a
    file path rather than accepting a DataFrame. Same math, different
    data source - not a new formula.
    """

    if price_history is None or len(price_history) < period + 1:
        return None

    df = price_history
    prev_close = df["close"].shift(1)

    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = float(true_range.rolling(window=period).mean().iloc[-1])

    return round(atr, 2) if not pd.isna(atr) else None


def load_historical_candidates():
    conn = sqlite3.connect(BACKTEST_DB_PATH)
    df = pd.read_sql("SELECT * FROM historical_candidates ORDER BY date", conn)
    conn.close()
    return df


def load_historical_regime():
    conn = sqlite3.connect(BACKTEST_DB_PATH)
    df = pd.read_sql("SELECT * FROM historical_regime", conn)
    conn.close()
    return df.set_index("date")


def run_full_backtest(total_capital=1000000, risk_per_trade_pct=0.005,
                       max_positions=10, max_per_sector=3,
                       concentration_cap_pct=0.20, same_bar_policy="STOP_FIRST",
                       require_volume_confirmation=True):

    print()
    print("=" * 70)
    print("FULL SWING-TRADING BACKTEST")
    print("=" * 70)
    print("Honest scope: Consolidation_Scanner.py only, sampled every 5 days.")
    print("Slippage and brokerage are NOT modeled in this first pass.")
    print()

    data = PointInTimeMarketData()
    candidates_df = load_historical_candidates()
    regime_df = load_historical_regime()

    if candidates_df.empty:
        print("[-] No historical candidates found - run Historical_Scanner_Reconstruction.py first.")
        return

    candidate_dates = sorted(candidates_df["date"].unique())
    print(f"[*] Processing {len(candidate_dates)} candidate dates, "
          f"{len(candidates_df)} total candidate-date combinations...")

    open_positions = {}   # ticker -> position dict
    closed_trades = []
    available_capital = total_capital
    sector_counts_by_open = {}

    for date_idx, date_str in enumerate(candidate_dates):

        as_of_date = pd.Timestamp(date_str)

        # Release any positions that have already closed by this date -
        # frees their capital and their MAX_POSITIONS slot before we
        # consider opening anything new today.
        for ticker in list(open_positions.keys()):
            pos = open_positions[ticker]
            if pos["exit_date"] is not None and pd.Timestamp(pos["exit_date"]) <= as_of_date:
                available_capital += pos["capital_used"] + pos["pnl"]
                closed_trades.append(pos)
                sector = pos.get("sector", "UNKNOWN")
                if sector in sector_counts_by_open:
                    sector_counts_by_open[sector] = max(0, sector_counts_by_open[sector] - 1)
                del open_positions[ticker]

        if date_idx > 0 and date_idx % 10 == 0:
            print(f"[*] Progress: {date_idx}/{len(candidate_dates)} dates, "
                  f"{len(closed_trades)} closed trades, {len(open_positions)} currently open...")

        regime_row = regime_df.loc[date_str] if date_str in regime_df.index else None
        regime = regime_row["regime"] if regime_row is not None else "NEUTRAL"
        position_multiplier = float(regime_row["position_multiplier"]) if regime_row is not None else 0.25

        todays_candidates = candidates_df[candidates_df["date"] == date_str]

        for _, cand in todays_candidates.iterrows():

            ticker = cand["ticker"]

            if ticker in open_positions:
                continue  # already holding this one

            if len(open_positions) >= max_positions:
                continue  # portfolio-wide position ceiling

            sector = get_sector(ticker)
            if sector != "UNKNOWN" and sector_counts_by_open.get(sector, 0) >= max_per_sector:
                continue  # sector concentration cap

            view = data.as_of(as_of_date)
            price_history = view.get_price_history(ticker)

            if price_history is None or len(price_history) < 15:
                continue

            price_now = float(price_history["close"].iloc[-1])
            pivot = float(cand["pivot"])
            trigger = pivot * 1.005

            if price_now < trigger:
                continue  # hasn't actually broken out yet

            if require_volume_confirmation:
                vol_ratio = compute_daily_volume_ratio(price_history)
                if vol_ratio is None or vol_ratio < 1.5:
                    continue  # honest RVOL proxy - no volume confirmation

            atr14 = compute_atr14_point_in_time(price_history)
            if atr14 is None or atr14 <= 0:
                continue

            stop = pivot - (1.5 * atr14)
            risk = pivot - stop

            if risk <= 0:
                continue

            risk_budget = total_capital * position_multiplier * risk_per_trade_pct
            shares = int(risk_budget / risk)

            max_shares_by_concentration = int((total_capital * concentration_cap_pct) / pivot)
            shares = min(shares, max_shares_by_concentration)

            capital_needed = shares * pivot

            if shares <= 0 or capital_needed > available_capital:
                continue

            t1_mult, t2_mult = calculate_dynamic_rr_multipliers(regime, float(cand["confidence"]))
            target_1 = pivot + t1_mult * risk
            target_2 = pivot + t2_mult * risk

            future_history = price_history  # will be re-fetched at the true final date below
            full_ticker_history = view._market_data.series_map.get(ticker)
            if full_ticker_history is None:
                continue

            price_history_after_entry = full_ticker_history[full_ticker_history.index >= as_of_date]

            result = simulate_trade(
                price_history_after_entry, entry_price=price_now, initial_stop=stop,
                target_1=target_1, target_2=target_2, shares=shares,
                same_bar_policy=same_bar_policy
            )

            available_capital -= capital_needed

            open_positions[ticker] = {
                "ticker": ticker, "sector": sector, "entry_date": date_str,
                "entry_price": price_now, "shares": shares, "capital_used": capital_needed,
                "stop": stop, "target_1": target_1, "target_2": target_2,
                "exit_reason": result["exit_reason"],
                "exit_date": result.get("exit_date"),
                "exit_price": result.get("exit_price"),
                "pnl": result.get("pnl", result.get("unrealized_pnl", 0)),
                "ambiguous_bars": result.get("ambiguous_bars", 0),
            }

            if sector != "UNKNOWN":
                sector_counts_by_open[sector] = sector_counts_by_open.get(sector, 0) + 1

    # Real bug found during testing: the release-closed-positions check
    # above only runs when processing a NEW candidate date - meaning a
    # position whose real exit_date falls after the LAST candidate date
    # in the whole dataset would never get moved into closed_trades,
    # even though simulate_trade() already determined its actual,
    # definite outcome. A final pass here catches every position that
    # genuinely has a known exit_date, regardless of whether the loop
    # ever reached a later date to check it.
    for ticker in list(open_positions.keys()):
        pos = open_positions[ticker]
        if pos["exit_date"] is not None:
            closed_trades.append(pos)
            del open_positions[ticker]

    # Anything still open at the end of available history
    still_open = list(open_positions.values())

    print(f"\n[+] Backtest complete: {len(closed_trades)} closed trades, "
          f"{len(still_open)} still open at end of data.")

    metrics = compute_backtest_metrics(closed_trades, total_capital)
    save_results(closed_trades, still_open, metrics)

    print_summary(metrics)

    print("=" * 70)


def compute_backtest_metrics(closed_trades, starting_capital):

    if not closed_trades:
        return {"total_trades": 0, "note": "No closed trades to analyze."}

    df = pd.DataFrame(closed_trades)

    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]

    total_pnl = df["pnl"].sum()
    win_rate = len(wins) / len(df) * 100 if len(df) > 0 else 0
    avg_win = wins["pnl"].mean() if not wins.empty else 0
    avg_loss = losses["pnl"].mean() if not losses.empty else 0
    profit_factor = (wins["pnl"].sum() / abs(losses["pnl"].sum())) if not losses.empty and losses["pnl"].sum() != 0 else None

    ambiguous_total = df["ambiguous_bars"].sum()

    return {
        "total_trades": len(df),
        "total_pnl": round(total_pnl, 2),
        "return_pct": round((total_pnl / starting_capital) * 100, 2),
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2) if avg_win else 0,
        "avg_loss": round(avg_loss, 2) if avg_loss else 0,
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "ambiguous_bars_total": int(ambiguous_total),
        "trades_with_ambiguity": int((df["ambiguous_bars"] > 0).sum()),
    }


def save_results(closed_trades, still_open, metrics):

    conn = sqlite3.connect(BACKTEST_DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_trades (
            ticker TEXT, sector TEXT, entry_date TEXT, entry_price REAL, shares INTEGER,
            exit_reason TEXT, exit_date TEXT, exit_price REAL, pnl REAL, ambiguous_bars INTEGER
        )
    """)

    if closed_trades:
        pd.DataFrame(closed_trades)[[
            "ticker", "sector", "entry_date", "entry_price", "shares",
            "exit_reason", "exit_date", "exit_price", "pnl", "ambiguous_bars"
        ]].to_sql("backtest_trades", conn, if_exists="replace", index=False)

    conn.close()

    manifest = dict(DEFAULT_ASSUMPTIONS)
    manifest["run_timestamp"] = datetime.now().isoformat()
    manifest["metrics"] = metrics
    manifest["still_open_count"] = len(still_open)

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assumptions_manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    print(f"[+] Trades written to backtest_trades, manifest written to {manifest_path}")


def print_summary(metrics):

    print("\n" + "-" * 70)
    print("RESULTS SUMMARY")
    print("-" * 70)
    for k, v in metrics.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    run_full_backtest()