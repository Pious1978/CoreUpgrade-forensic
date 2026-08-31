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
from Trade_Journal import get_remaining_shares


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


def compute_rs_line_drawdown(ticker, lookback=252):
    """
    Real "consistency of leadership" metric, adapted from Alpha1's
    Emerging_Leader_Scanner.py - the RS line (stock price divided by
    the NIFTYBEES benchmark) is a classic technical analysis concept.
    Its max drawdown over the past year tells you something a
    point-in-time RS percentile can't: has this stock's relative
    outperformance ever suffered a real setback, or has its leadership
    been genuinely persistent? Two stocks can share today's RS
    percentile while having very different consistency underneath it.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")
    bench_path = os.path.join(PARQUET_CACHE_DIR, "NIFTYBEES.parquet")

    if not os.path.exists(path) or not os.path.exists(bench_path):
        return None

    try:
        stock_df = pd.read_parquet(path).sort_values("date").set_index("date")
        bench_df = pd.read_parquet(bench_path).sort_values("date").set_index("date")

        aligned = pd.DataFrame({
            "stock": stock_df["close"],
            "benchmark": bench_df["close"],
        }).dropna()

        if len(aligned) < lookback:
            return None

        rs_line = (aligned["stock"] / aligned["benchmark"]).tail(lookback)
        drawdown = (rs_line / rs_line.cummax() - 1).min()

        return round(float(drawdown) * 100, 2)

    except Exception:
        return None


def count_gap_shocks(ticker, threshold_pct=12.0, window=20):
    """
    Real "erratic, news-driven risk" check, adapted from Alpha1's
    Emerging_Leader_Scanner.py - counts genuine overnight gaps (open
    vs previous close) exceeding threshold_pct within the last window
    trading days. Distinct from regular intraday volatility (ATR):
    this specifically measures gap/news risk, not normal price
    movement during the trading session itself.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path).sort_values("date")

        if len(df) < window + 1:
            return None

        prev_close = df["close"].shift(1)
        gaps_pct = ((df["open"] - prev_close) / prev_close).abs() * 100

        return int((gaps_pct.tail(window) > threshold_pct).sum())

    except Exception:
        return None


def compute_measured_move_target(ticker, pivot, lookback=60):
    """
    Real "measured move" technical analysis concept, confirmed in
    Trade_Execution_Engine.py's own docstring as a real, historical
    change made to that script's target-setting methodology - target
    = pivot + base height, where base height is the pivot's distance
    above the low of the recent consolidation range it's breaking out
    of. A classic idea: the size of the base a stock built often
    projects roughly how far the breakout can travel.

    Genuinely an alternative reference point alongside our existing
    dynamic R:R targets, not a replacement - the two methods can
    legitimately disagree, and seeing both is more informative than
    either alone. Uses a defensible, simple approximation for "where
    is the base's low point" (the lowest low over a trailing 60-day
    window) rather than genuine pattern-recognition of exactly where
    a specific base started and ended.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    if pivot is None:
        return None

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path).sort_values("date")

        if len(df) < lookback:
            return None

        base_low = float(df["low"].tail(lookback).min())
        base_height = pivot - base_low

        if base_height <= 0:
            return None

        target = round(pivot + base_height, 2)

        return {
            "target": target,
            "base_height": round(base_height, 2),
            "base_low": round(base_low, 2),
        }

    except Exception:
        return None


def compute_ema_slope_persistence(ticker):
    """
    Real, simple addition adapted from Alpha1's Pullback_Analyzer.py -
    checks whether the EMA20/EMA50 lines themselves are actively rising
    over the past 5 days, not just whether price sits above them.
    Genuinely different information from classify_pullback()'s static
    price-vs-EMA comparison: an EMA that's flattening or rolling over
    signals weakening trend quality even if price still happens to sit
    above it today.
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

        ema20 = df["close"].ewm(span=20, adjust=False).mean()
        ema50 = df["close"].ewm(span=50, adjust=False).mean()

        ema20_rising = bool(ema20.iloc[-1] > ema20.iloc[-5])
        ema50_rising = bool(ema50.iloc[-1] > ema50.iloc[-5])

        if ema20_rising and ema50_rising:
            note = "both EMA20 and EMA50 actively rising - real trend persistence"
        elif ema20_rising:
            note = "EMA20 rising but EMA50 flat/falling - shorter-term strength only"
        elif ema50_rising:
            note = "EMA50 rising but EMA20 flat/falling - longer trend intact, near-term stalling"
        else:
            note = "neither EMA rising - trend quality weakening, even if price is above them"

        return {
            "ema20_rising": ema20_rising,
            "ema50_rising": ema50_rising,
            "note": note,
        }

    except Exception:
        return None


def check_already_holding(ticker):
    """
    Real "am I already holding this?" check against our own trade_journal
    - genuinely simpler than the fuzzy company-name matching Alpha1's
    original version needed, since our system already tracks holdings
    by ticker directly, not company names from a manually-maintained
    Excel statement. Aggregates across multiple tranches (bought on
    different dates) into one summary rather than only showing the
    first match, since a real position can genuinely be built up over
    several separate entries.
    """

    try:
        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute("""
            SELECT id, entry_price, entry_shares, entry_date
            FROM trade_journal
            WHERE UPPER(ticker) = ? AND status = 'EXECUTED'
            ORDER BY entry_date ASC
        """, (ticker.upper(),)).fetchall()

        tranches = []
        total_remaining = 0
        total_cost = 0.0

        for journal_id, entry_price, entry_shares, entry_date in rows:
            remaining = get_remaining_shares(conn, journal_id, entry_shares)

            if remaining > 0:
                tranches.append((entry_date, entry_price, remaining))
                total_remaining += remaining
                total_cost += entry_price * remaining

        conn.close()

        if total_remaining <= 0:
            return None

        avg_price = round(total_cost / total_remaining, 2)

        return {
            "total_shares": total_remaining,
            "avg_price": avg_price,
            "tranche_count": len(tranches),
            "tranches": tranches,
        }

    except Exception:
        return None


def compute_vcr(ticker):
    """
    Volatility Contraction Ratio - adapted from a real, working idea in
    Alpha1's Swing.py. Simple, directly interpretable, unlike our
    base_compression factor (an opaque percentile-rank score): recent
    10-day average daily range as a fraction of the 60-day average.
    Below 1.0 means volatility is genuinely tightening relative to its
    own recent history - a real, real-time VCP/compression signal.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close", "high", "low"])

        if len(df) < 60:
            return None

        df["daily_range_pct"] = ((df["high"] - df["low"]) / df["close"]) * 100
        recent_vol = df["daily_range_pct"].tail(10).mean()
        historic_vol = df["daily_range_pct"].tail(60).mean()

        if historic_vol == 0 or pd.isna(historic_vol):
            return None

        return round(recent_vol / historic_vol, 2)

    except Exception:
        return None


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


def fetch_quick_fundamentals(ticker):
    """
    Fast, single-call fundamentals context for a spiking stock - NOT the
    deep Compounder_Scanner.py quality gate. This is informational
    context alongside the existing technical read, never a pass/fail
    gate - a spiking stock can be a legitimate momentum trade even
    without "compounder" quality. Returns None on any failure so a
    fundamentals hiccup never blocks the rest of the lookup.
    """

    try:
        import yfinance as yf
    except ImportError:
        return None

    from core.symbol_utils import fetch_yfinance_info

    try:
        info = fetch_yfinance_info(ticker)

        if not info:
            return None

        return {
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margin": info.get("profitMargins"),
            "roe": info.get("returnOnEquity"),
        }

    except Exception:
        return None


def assess_fundamentals(fundamentals):
    """
    Lightweight, informational notes only - never blocks or rejects.
    Deliberately more lenient than Compounder_Scanner.py's strict
    quality gate (12% ROE / 150% debt / 5% margin), since the point
    here is quick context on a fast-moving stock, not a full
    quality-investing screen.
    """

    if not fundamentals:
        return ["Fundamentals unavailable"]

    notes = []

    margin = fundamentals.get("profit_margin")
    if margin is not None and margin < 0:
        notes.append("LOSING MONEY - exercise extra caution chasing this move")

    debt = fundamentals.get("debt_to_equity")
    if debt is not None and debt > 300:
        notes.append(f"HIGH DEBT (D/E {debt}) - balance sheet risk, verify before sizing up")

    trailing_pe = fundamentals.get("trailing_pe")
    forward_pe = fundamentals.get("forward_pe")
    if trailing_pe and forward_pe and trailing_pe > 0:
        if forward_pe < trailing_pe * 0.8:
            notes.append(f"Forward PE ({forward_pe}) well below trailing ({trailing_pe}) - earnings expected to grow")
        elif forward_pe > trailing_pe * 1.2:
            notes.append(f"Forward PE ({forward_pe}) well above trailing ({trailing_pe}) - earnings expected to decline")

    if not notes:
        notes.append("No red flags from quick fundamentals check")

    return notes


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

    holding = check_already_holding(ticker)
    if holding:
        unrealized_pct = round((price - holding["avg_price"]) / holding["avg_price"] * 100, 2)
        tranche_note = f" across {holding['tranche_count']} tranches" if holding["tranche_count"] > 1 else ""
        print(f"  [!] Already holding: {holding['total_shares']} shares @ avg Rs{holding['avg_price']}{tranche_note}  "
              f"({unrealized_pct:+.2f}% unrealized)")

    watchlist_row = get_existing_watchlist_row(conn, ticker)

    _, atr_pct = compute_atr(ticker)
    atr_abs = None
    if atr_pct is not None:
        atr_abs = round(price * atr_pct / 100, 2)

    weekly_rvol = compute_weekly_rvol(ticker)
    tech = get_technical_context(ticker)

    if watchlist_row is not None and pd.notna(watchlist_row.get("pivot_price")):
        pivot = float(watchlist_row["pivot_price"])
        pattern = watchlist_row.get("pattern", "N/A")
        tier = watchlist_row.get("Tier", "N/A")
        source = "from tonight's overnight scan"
    elif watchlist_row is not None:
        # Real, confirmed case (MAHLIFE) - a stock can genuinely have a
        # watchlist row (it cleared the tier/composite score cut) while
        # still having a NULL pivot_price specifically, if the overnight
        # scan couldn't compute a valid pivot for it. Previously crashed
        # here; now falls back to the same computed pivot used for
        # stocks with no watchlist row at all, while still showing the
        # real pattern/tier info we do have.
        pivot, stop_fallback = compute_fallback_pivot_and_stop(ticker, price, atr_abs)
        pattern = watchlist_row.get("pattern", "N/A")
        tier = watchlist_row.get("Tier", "N/A")
        source = "estimated (20-day high) - flagged by the overnight scan, but no pivot was computed for it"
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

    measured_move = compute_measured_move_target(ticker, pivot)
    if measured_move:
        print(f"  Measured Move: Rs{measured_move['target']:.2f}  "
              f"(alternative - pivot + base height, base low Rs{measured_move['base_low']:.2f})")

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

    slope = compute_ema_slope_persistence(ticker)
    if slope:
        print(f"  EMA Slope        : {slope['note']}")

    vcr = compute_vcr(ticker)
    if vcr is not None:
        if vcr < 0.6:
            vcr_note = "genuinely tightening - real, current VCP-style compression"
        elif vcr < 1.0:
            vcr_note = "mildly contracting"
        elif vcr < 1.5:
            vcr_note = "normal / mixed"
        else:
            vcr_note = "expanding - not a tight setup right now"
        print(f"  VCR              : {vcr}  ({vcr_note})")

    rs_drawdown = compute_rs_line_drawdown(ticker)
    if rs_drawdown is not None:
        if rs_drawdown > -10:
            drawdown_note = "very persistent relative leadership"
        elif rs_drawdown > -20:
            drawdown_note = "reasonably consistent leadership"
        else:
            drawdown_note = "choppy - relative outperformance has had real setbacks"
        print(f"  RS Line Drawdown : {rs_drawdown}%  ({drawdown_note})")

    gap_shocks = count_gap_shocks(ticker)
    if gap_shocks is not None and gap_shocks > 0:
        print(f"  [!] Gap Shocks   : {gap_shocks} overnight gap(s) >12% in the last 20 days - "
              f"erratic, news-driven risk, distinct from normal volatility")

    print("-" * 68)
    fundamentals = fetch_quick_fundamentals(ticker)
    fund_notes = assess_fundamentals(fundamentals)

    if fundamentals:
        pe_str = f"{fundamentals.get('trailing_pe')}" if fundamentals.get("trailing_pe") else "N/A"
        pb_str = f"{fundamentals.get('price_to_book')}" if fundamentals.get("price_to_book") else "N/A"
        roe_str = f"{round(fundamentals.get('roe')*100, 1)}%" if fundamentals.get("roe") else "N/A"
        print(f"  Quick Fundamentals: PE {pe_str}  |  PB {pb_str}  |  ROE {roe_str}")

    for note in fund_notes:
        print(f"    -> {note}")

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