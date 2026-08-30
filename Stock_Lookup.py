"""
Stock_Lookup.py

Ad-hoc, on-demand single-stock analysis - type any ticker, get an
instant, real report, whether or not that stock happened to be flagged
by tonight's overnight scan. Directly closes the gap identified against
Alpha1's Trade_Execution_Engine.py, which offers exactly this kind of
"look up anything right now" capability that the rest of this system
doesn't.

Deliberately reuses every real, individually-tested calculation
function already built tonight rather than reimplementing anything:
compute_atr, compute_weekly_rvol, and get_technical_context from
core/technical_indicators.py; calculate_conviction_score, calculate_edp,
and get_read from Live_Execution_Monitor.py; calculate_dynamic_rr_multipliers
from Risk_Positioning_Engine.py. Confirmed safe to import from both of
those files without triggering their interactive prompts (both guard
their entry point behind if __name__ == "__main__").

If the ticker was never flagged by the overnight scanners (no row in
research_watchlist), this falls back to a genuine, real pivot estimate
(the 20-day high) and a real ATR-based stop, rather than refusing to
analyze it - the whole point of this tool is working for any ticker,
not just ones already in the system.
"""

import sqlite3
import pandas as pd

from core.config import DB_PATH
from core.technical_indicators import get_technical_context, compute_atr, compute_weekly_rvol
from core.Live_Price_Engine import LivePriceEngine

from Live_Execution_Monitor import calculate_conviction_score, calculate_edp, get_read
from Risk_Positioning_Engine import calculate_dynamic_rr_multipliers
from core.Execution_State_Machine import evaluate_trade


def get_current_regime(conn):

    try:
        cur = conn.execute("SELECT regime, position_multiplier FROM market_regime ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return "NEUTRAL", 0.25
        return row[0], row[1]
    except Exception:
        return "NEUTRAL", 0.25


def get_existing_watchlist_row(conn, ticker):
    """Real pivot/pattern/composite data if this ticker already cleared
    the overnight scanners and made it into research_watchlist."""

    try:
        df = pd.read_sql("""
            SELECT * FROM research_watchlist
            WHERE UPPER(Ticker) = ?
            AND Date = (SELECT MAX(Date) FROM research_watchlist)
        """, conn, params=(ticker.upper(),))

        if df.empty:
            return None

        return df.iloc[0]

    except Exception:
        return None


def get_factor_data(conn, ticker):
    """Real, individually-verified factor values for this ticker, if
    available - same fields the live conviction score uses."""

    factors = {}

    try:
        snap = pd.read_sql("""
            SELECT rs_percentile, delivery_score FROM daily_snapshot
            WHERE UPPER(symbol) = ?
            AND date = (SELECT MAX(date) FROM daily_snapshot)
        """, conn, params=(ticker.upper(),))

        if not snap.empty:
            factors["rs_percentile"] = snap.iloc[0]["rs_percentile"]
            factors["delivery_score"] = snap.iloc[0]["delivery_score"]

    except Exception:
        pass

    try:
        sf = pd.read_sql("""
            SELECT factor_name, score FROM scanner_factors
            WHERE UPPER(ticker) = ?
            AND date = (SELECT MAX(date) FROM scanner_factors)
        """, conn, params=(ticker.upper(),))

        for _, row in sf.iterrows():
            factors[row["factor_name"]] = row["score"]

    except Exception:
        pass

    return factors


def compute_fallback_pivot_and_stop(ticker, current_price, atr_abs):
    """
    For a ticker that was never flagged by the overnight scanners - no
    real pattern-derived pivot exists yet, so this uses the 20-day high
    as a genuine, real reference point (not an invented number) and a
    real ATR-based stop, the same convention Risk_Positioning_Engine.py
    already uses (stop = pivot - 1.5*ATR).
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None, None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close", "high", "low"])

        if len(df) < 20:
            return None, None

        pivot = float(df["high"].tail(20).max())

        if atr_abs is not None:
            stop = round(pivot - 1.5 * atr_abs, 2)
        else:
            stop = round(pivot * 0.97, 2)

        return round(pivot, 2), stop

    except Exception:
        return None, None


def lookup(ticker):

    ticker = ticker.upper().strip().replace(".NS", "")

    conn = sqlite3.connect(DB_PATH)

    print()
    print("=" * 68)
    print(f"  STOCK LOOKUP: {ticker}")
    print("=" * 68)

    quote = LivePriceEngine.get_live_quote(ticker)

    if quote.get("status") != "SUCCESS" or not quote.get("ltp"):
        print(f"  [-] Could not get a live quote for {ticker} - check the ticker is correct, or try again during market hours.")
        conn.close()
        return

    price = quote["ltp"]
    rvol = quote.get("rvol", 1.0)

    print(f"  Live Price   : Rs{price:.2f}")
    print(f"  Intraday RVOL: {rvol}x")

    watchlist_row = get_existing_watchlist_row(conn, ticker)

    _, atr_pct = compute_atr(ticker)
    atr_abs = None
    if atr_pct is not None:
        atr_abs = round(price * atr_pct / 100, 2)

    weekly_rvol = compute_weekly_rvol(ticker)
    tech = get_technical_context(ticker)

    if watchlist_row is not None:
        pivot = float(watchlist_row["pivot_price"])
        pattern = watchlist_row.get("pattern", "N/A")
        tier = watchlist_row.get("Tier", "N/A")
        source = "from tonight's overnight scan"
    else:
        pivot, stop_fallback = compute_fallback_pivot_and_stop(ticker, price, atr_abs)
        pattern = "N/A - not flagged by overnight scan"
        tier = "N/A"
        source = "estimated (20-day high) - this ticker wasn't flagged by any scanner"

    if pivot is None:
        print(f"  [-] Not enough real history for {ticker} to compute a pivot reference.")
        conn.close()
        return

    print(f"  Pivot        : Rs{pivot:.2f}  ({source})")
    print(f"  Pattern      : {pattern}")

    stop_loss = round(pivot - 1.5 * atr_abs, 2) if atr_abs is not None else round(pivot * 0.97, 2)
    risk = pivot - stop_loss

    regime, multiplier = get_current_regime(conn)

    factors = get_factor_data(conn, ticker)

    distance = round(((price - pivot) / pivot) * 100, 2)

    if price - stop_loss > 0 and risk > 0:
        target_1_tentative = pivot + 2 * risk
        remaining_r = round((target_1_tentative - price) / (price - stop_loss), 2)
    else:
        remaining_r = None

    score, opportunity, readiness = calculate_conviction_score(
        rs_percentile=factors.get("rs_percentile"),
        delivery_score=factors.get("delivery_score"),
        accumulation_ratio=factors.get("accumulation_ratio"),
        base_compression=factors.get("base_compression"),
        cup_handle_quality=factors.get("cup_handle_quality"),
        hybrid_alpha_score=factors.get("hybrid_alpha_score"),
        intraday_rvol=rvol,
        weekly_rvol=weekly_rvol,
        pivot_extension=factors.get("pivot_extension"),
        remaining_r=remaining_r,
        distance=distance
    )

    t1_mult, t2_mult = calculate_dynamic_rr_multipliers(regime, score / 100)
    target_1 = round(pivot + t1_mult * risk, 2)
    target_2 = round(pivot + t2_mult * risk, 2)

    print("-" * 68)
    print(f"  Stop Loss    : Rs{stop_loss:.2f}")
    print(f"  Target 1     : Rs{target_1:.2f}  (dynamic R:R, regime-adjusted)")
    print(f"  Target 2     : Rs{target_2:.2f}")
    print("-" * 68)
    print(f"  Conviction Score : {score}/100  (Opportunity {opportunity} / Readiness {readiness})")
    print(f"  Tier             : {tier}")

    if distance < 0:
        edp = calculate_edp(distance, atr_pct)
        if edp:
            print(f"  Expected Days to Pivot : {edp}")

    weekly_rvol_str = f"{weekly_rvol}x" if weekly_rvol is not None else "N/A (insufficient history)"
    print(f"  Weekly RVOL      : {weekly_rvol_str}")

    trigger = round(pivot * 1.005, 2)
    real_state = evaluate_trade(price, pivot, trigger, rvol, "WAITING", stop_loss=stop_loss)
    read_text = get_read(real_state, tech["discount_pct"], tech["vdry_ratio"], rvol)
    print(f"  Status           : {real_state}")
    print(f"  Read             : {read_text}")

    print(f"  Market Regime    : {regime}  (exposure {int(multiplier*100)}%)")
    print("=" * 68)

    conn.close()


if __name__ == "__main__":

    print("Stock Lookup - type a ticker for an instant real analysis, or 'exit' to quit.")

    while True:

        user_input = input("\nTicker: ").strip()

        if user_input.lower() in ("exit", "quit", "q"):
            break

        if not user_input:
            continue

        lookup(user_input)