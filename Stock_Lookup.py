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


def compute_ema50(ticker):
    """
    Local, small calculation - EMA20 already comes from
    get_technical_context(), but EMA50 isn't part of that shared
    function. Kept separate here rather than modifying that shared
    function, since EMA50 is only needed for this tool's pullback
    classification, not anywhere else in the live board.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path).sort_values("date")

        if len(df) < 55:
            return None

        return round(float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1]), 2)

    except Exception:
        return None


def classify_pullback(price, ema20, ema50):
    """
    Adapted from Alpha1's real Trade_Execution_Engine.py - a
    complementary classification to our own pivot-based state machine
    (BASE_BUILDING/APPROACHING/TESTING/breakout states, all relative to
    a pattern-derived pivot). This recognizes something different: a
    stock in a genuine uptrend (EMA20 > EMA50) that has pulled back
    below EMA20 - the classic "buy the dip in an established trend"
    setup, which our pivot-relative state machine has no equivalent for.
    """

    if ema20 is None or ema50 is None:
        return None

    if ema20 > ema50 and price < ema20:
        return "PULLBACK_ENTRY - price below EMA20 in an established uptrend (EMA20 > EMA50), classic buy-the-dip setup"

    return None


def get_size_factor(atr_pct):
    """
    Adapted from Alpha1's real Trade_Execution_Engine.py - a genuine
    second layer of risk control on top of the stop-distance-based
    sizing we already do. A wider stop on a volatile stock already
    reduces share count once; this additionally reduces it further for
    genuinely high-ATR% stocks, and allows slightly larger size for
    genuinely low-ATR% ones, rather than trusting stop-distance math
    alone.
    """

    if atr_pct is None:
        return 1.0

    atr_fraction = atr_pct / 100

    if atr_fraction > 0.05:
        return 0.75
    elif atr_fraction < 0.02:
        return 1.25
    else:
        return 1.0


def lookup(ticker, capital=None, risk_pct=None):

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

    ema50 = compute_ema50(ticker)
    pullback_note = classify_pullback(price, tech.get("ema20"), ema50)
    if pullback_note:
        print(f"  Also             : {pullback_note}")

    print(f"  Market Regime    : {regime}  (exposure {int(multiplier*100)}%)")

    if capital is not None and risk_pct is not None and risk > 0:

        risk_amt = capital * (risk_pct / 100)
        size_factor = get_size_factor(atr_pct)
        qty = int((risk_amt * size_factor) / risk)
        capital_used = round(qty * price, 2)

        print("-" * 68)
        print(f"  Suggested Qty    : {qty} shares  (Rs{capital_used:,.0f} used)")

        if size_factor != 1.0:
            note = "reduced - high volatility (ATR)" if size_factor < 1.0 else "increased - low volatility (ATR)"
            print(f"    -> size factor {size_factor}x applied ({note})")

    print("=" * 68)

    conn.close()


if __name__ == "__main__":

    print("Stock Lookup - type a ticker for an instant real analysis, or 'exit' to quit.")
    print()
    print("When to trust this tool's read:")
    print("  - Avoid the first 15 min after open (9:15-9:30) - RVOL is unreliable")
    print("    before real volume has built up; a dramatic-looking ratio here is")
    print("    often just opening-auction noise, not a genuine signal.")
    print("  - ~9:30-9:45 onward is the first genuinely trustworthy checkpoint.")
    print("  - Best used reactively - the moment something catches your eye or")
    print("    triggers an alert - rather than on a fixed schedule.")
    print("  - If sweeping proactively, ~11:30-12:00 or ~2:30-3:00 are cleaner")
    print("    windows than midday, which often sees a real lull.")

    capital = None
    risk_pct = None

    size_answer = input("\nWant position sizing too? Enter capital (Rs), or blank to skip: ").strip()

    if size_answer:
        try:
            capital = float(size_answer)
            risk_pct = float(input("Risk per trade as a % (e.g. 1 for 1%): ").strip())
        except ValueError:
            print("Invalid number - continuing without position sizing.")
            capital = None
            risk_pct = None

    while True:

        user_input = input("\nTicker: ").strip()

        if user_input.lower() in ("exit", "quit", "q"):
            break

        if not user_input:
            continue

        lookup(user_input, capital=capital, risk_pct=risk_pct)