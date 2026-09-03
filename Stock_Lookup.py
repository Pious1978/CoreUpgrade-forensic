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

from Live_Execution_Monitor import calculate_conviction_score, calculate_edp, get_read, EXTENSION_REJECT_PCT
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


def compute_fibonacci_value_zone(ticker, rr_ratio=2.0):
    """
    The ORIGINAL "Value Zone" - a real, working concept found consistently
    across 4 of the user's own past tools (Scanning_Tool.py,
    research_analyst.py, alpha_strategist.py, research_update.py):
    a Fibonacci 61.8% retracement level over a 6-month window, purely
    price-based - genuinely unrelated to compute_value_zone()'s
    fundamentals-based check despite the shared "Value Zone" name.
    Both are kept, clearly distinctly labeled, to avoid any ambiguity
    about which concept a given line refers to.

    Reuses the exact real formula found in the legacy tools:
    fib_value_zone = high_6m - (0.618 * (high_6m - low_6m))
    stop_loss = low_6m
    signal = VALUE BUY if current price is within 5% of the zone
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

        if len(df) < 126:  # ~6 months of trading days, matching the original's period="6mo"
            return None

        window = df.tail(126)
        high_6m = float(window["high"].max())
        low_6m = float(window["low"].min())
        close_p = float(df["close"].iloc[-1])

        if high_6m <= low_6m:
            return None

        fib_zone = high_6m - (0.618 * (high_6m - low_6m))
        stop_loss = low_6m
        risk_amt = fib_zone - stop_loss

        if risk_amt <= 0:
            return None

        target = fib_zone + (risk_amt * rr_ratio)
        signal = "VALUE BUY" if close_p <= (fib_zone * 1.05) else "WAITING"

        return {
            "signal": signal,
            "fib_zone": round(fib_zone, 2),
            "stop_loss": round(stop_loss, 2),
            "target": round(target, 2),
            "current_price": round(close_p, 2),
            "high_6m": round(high_6m, 2),
            "low_6m": round(low_6m, 2),
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


def compute_vcp_signal(ticker):
    """
    #61 - Combined binary VCP signal, adapted from a real, working idea
    found in Alpha1/Obsolete/smallcap_volatility_scanner.py: a single,
    direct "VCP_DETECTED" flag combining tightness + trend + proximity
    to highs, rather than checking several separate factors
    individually. Reuses compute_vcr() and compute_ema_slope_persistence()
    exactly as-is - "same logic, combined differently," not a
    duplicated calculation.

    Conditions, all three required:
    - Tightness: VCR < 1.0 (volatility genuinely contracting)
    - Trend: both EMA20 and EMA50 actively rising
    - Proximity: within 8% of the 52-week high
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

        if len(df) < 252:
            return None

        vcr = compute_vcr(ticker)
        slope = compute_ema_slope_persistence(ticker)

        if vcr is None or slope is None:
            return None

        current_close = float(df["close"].iloc[-1])
        high_52w = float(df["high"].tail(252).max())

        if high_52w <= 0:
            return None

        pct_below_high = ((high_52w - current_close) / high_52w) * 100

        tightness_ok = vcr < 1.0
        trend_ok = slope["ema20_rising"] and slope["ema50_rising"]
        proximity_ok = pct_below_high <= 8.0

        vcp_detected = tightness_ok and trend_ok and proximity_ok

        return {
            "vcp_detected": vcp_detected,
            "vcr": vcr,
            "trend_ok": trend_ok,
            "pct_below_52w_high": round(pct_below_high, 2),
        }

    except Exception:
        return None


def compute_breakout_checklist(ticker, price, pivot, rvol, real_state, distance):
    """
    #65 - Explicit breakout-volume requirement checklist. Combines
    already-computed values (price/pivot/rvol/state/distance) with two
    new, small calculations from real parquet_cache data: volume vs the
    20-day average (a genuinely different baseline than intraday RVOL,
    which compares to typical pace at this time of day, not the recent
    daily average), and how many consecutive recent days price has
    closed at or above the pivot. Retest success reuses
    Execution_State_Machine.py's real RETEST_SUCCESS state directly,
    not a new, separate definition.
    """

    import os
    import pandas as pd
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    volume_vs_20d_avg = None
    days_above_pivot = 0

    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            df.columns = [str(c).lower() for c in df.columns]
            df = df.dropna(subset=["close", "volume"]).sort_values("date")

            if len(df) >= 21:
                today_volume = float(df["volume"].iloc[-1])
                prior_20d_avg = float(df["volume"].iloc[-21:-1].mean())
                if prior_20d_avg > 0:
                    volume_vs_20d_avg = round(today_volume / prior_20d_avg, 2)

            recent_closes = df["close"].tail(10).tolist()
            for close_val in reversed(recent_closes):
                if close_val >= pivot:
                    days_above_pivot += 1
                else:
                    break

        except Exception:
            pass

    return {
        "pivot_crossed": price >= pivot,
        "breakout_rvol": rvol,
        "volume_vs_20d_avg": volume_vs_20d_avg,
        "close_above_pivot": price >= pivot,
        "pct_above_pivot": distance,
        "days_above_pivot": days_above_pivot,
        "retest_successful": real_state == "RETEST_SUCCESS",
    }


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
            # Added for the fundamentals-based Value Zone - all from this
            # same .info call, zero extra API cost
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "peg_ratio": info.get("pegRatio"),
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


def find_sector_peers(ticker, max_peers=5):
    """
    Real peer tickers from the same sector, via core/sector_map.py's
    curated UNIVERSE - a reverse lookup, not a new data source. Capped
    at max_peers since each peer requires a real, live fetch (the
    fundamentals Value Zone's peer dimension is genuinely slower than
    the rest of the quick lookup as a result - an honest tradeoff, not
    hidden).
    """

    from core.sector_map import UNIVERSE, get_sector

    target_sector = get_sector(ticker)

    if target_sector == "UNKNOWN":
        return []

    clean_ticker = ticker.upper().strip()
    if not clean_ticker.endswith(".NS"):
        clean_ticker += ".NS"

    peers = [
        t.replace(".NS", "") for t, info in UNIVERSE.items()
        if info["sector"] == target_sector and t != clean_ticker
    ]

    return peers[:max_peers]


def compute_value_zone(ticker, fundamentals):
    """
    Fundamentals-based Value Zone - genuinely different from
    compute_fibonacci_value_zone()'s price-based concept despite the
    shared name (see that function's docstring for the full context).
    Combines 4 dimensions: own historical range, absolute Graham-style
    thresholds, sector-peer comparison, and PEG ratio. Each dimension
    is scored independently and reported transparently - a stock can
    be "cheap" on one dimension and "expensive" on another; this shows
    all of them rather than collapsing to one misleading number.

    HONEST LIMITATION on the "own historical range" dimension: a true
    historical PE range needs historical EPS data, which isn't
    reliably available through this codebase's existing yfinance
    usage. Uses price position within the real 52-week high/low range
    as an honest, disclosed proxy instead.
    """

    if not fundamentals:
        return None

    result = {
        "historical_range": None,
        "graham_style": None,
        "sector_peer": None,
        "peg": None,
    }

    price = fundamentals.get("current_price")
    high_52w = fundamentals.get("fifty_two_week_high")
    low_52w = fundamentals.get("fifty_two_week_low")

    if price and high_52w and low_52w and high_52w > low_52w:
        position = (price - low_52w) / (high_52w - low_52w)
        if position <= 0.30:
            result["historical_range"] = f"NEAR OWN 52-WEEK LOW ({position*100:.0f}% of range) - proxy for cheap vs own history"
        elif position >= 0.70:
            result["historical_range"] = f"NEAR OWN 52-WEEK HIGH ({position*100:.0f}% of range) - proxy for expensive vs own history"
        else:
            result["historical_range"] = f"MID-RANGE ({position*100:.0f}% of own 52-week range)"

    pe = fundamentals.get("trailing_pe")
    pb = fundamentals.get("price_to_book")
    roe = fundamentals.get("roe")

    if pe and pb and pe > 0 and pb > 0:
        graham_number = pe * pb
        roe_ok = roe is not None and roe >= 0.12
        if graham_number < 22.5 and roe_ok:
            result["graham_style"] = f"VALUE ZONE (PE×PB={graham_number:.1f} < 22.5, ROE {roe*100:.1f}% >= 12%)"
        elif graham_number < 22.5:
            roe_display = f"{roe*100:.1f}%" if roe is not None else "unavailable"
            result["graham_style"] = f"Cheap by PE×PB ({graham_number:.1f}) but ROE too low or unavailable ({roe_display})"
        else:
            result["graham_style"] = f"NOT in value zone (PE×PB={graham_number:.1f} >= 22.5)"

    if pe and pe > 0:
        peers = find_sector_peers(ticker)
        peer_pes = []

        for peer in peers:
            peer_fundamentals = fetch_quick_fundamentals(peer)
            if peer_fundamentals and peer_fundamentals.get("trailing_pe"):
                peer_pes.append(peer_fundamentals["trailing_pe"])

        if peer_pes:
            import statistics
            peer_median_pe = statistics.median(peer_pes)
            if pe < peer_median_pe * 0.85:
                result["sector_peer"] = f"CHEAPER than sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, n={len(peer_pes)})"
            elif pe > peer_median_pe * 1.15:
                result["sector_peer"] = f"MORE EXPENSIVE than sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, n={len(peer_pes)})"
            else:
                result["sector_peer"] = f"IN LINE with sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, n={len(peer_pes)})"
        else:
            result["sector_peer"] = "No peer PE data available for comparison"

    peg = fundamentals.get("peg_ratio")
    if peg is not None:
        if peg < 1.0:
            result["peg"] = f"PEG {peg:.2f} < 1.0 - potentially undervalued relative to growth"
        elif peg > 2.0:
            result["peg"] = f"PEG {peg:.2f} > 2.0 - potentially overvalued relative to growth"
        else:
            result["peg"] = f"PEG {peg:.2f} - fairly valued relative to growth"
    else:
        result["peg"] = "PEG ratio unavailable"

    return result


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

    # #64 - explicit extension warning, reusing Live_Execution_Monitor.py's
    # real EXTENSION_REJECT_PCT threshold (already used there to reject
    # sizing on an over-extended entry) rather than inventing a new,
    # separate number here.
    is_extended = distance > EXTENSION_REJECT_PCT

    if is_extended:
        print(f"  ⚠ EXTENDED   : {distance:+.1f}% from pivot, beyond the {EXTENSION_REJECT_PCT}% threshold - "
              f"don't chase this without genuinely strong momentum justification")

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

    # #63 - measured from PIVOT, not current price: the realistic entry
    # point is at/near the pivot (trigger = pivot * 1.005), not wherever
    # price happens to be right now while still approaching. Reward
    # assessed from an assumed entry price the trade doesn't actually
    # have yet was misleading, per real, direct feedback.
    stop_pct_from_pivot = round(((stop_loss - pivot) / pivot) * 100, 1) if pivot > 0 else None
    t1_pct_from_pivot = round(((target_1 - pivot) / pivot) * 100, 1) if pivot > 0 else None
    t2_pct_from_pivot = round(((target_2 - pivot) / pivot) * 100, 1) if pivot > 0 else None

    stop_suffix = f"  ({stop_pct_from_pivot:+}% from pivot)" if stop_pct_from_pivot is not None else ""
    t1_suffix = f"  ({t1_pct_from_pivot:+}% from pivot)" if t1_pct_from_pivot is not None else ""
    t2_suffix = f"  ({t2_pct_from_pivot:+}% from pivot)" if t2_pct_from_pivot is not None else ""

    print("-" * 68)
    print(f"  Stop Loss    : Rs{stop_loss:.2f}{stop_suffix}")
    print(f"  Target 1     : Rs{target_1:.2f}  (dynamic R:R, regime-adjusted){t1_suffix}")
    print(f"  Target 2     : Rs{target_2:.2f}{t2_suffix}")

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

    # #65 - explicit breakout-volume requirement checklist, the real
    # criteria responsible for turning APPROACHING into VALID_BREAKOUT,
    # made visible rather than implied.
    checklist = compute_breakout_checklist(ticker, price, pivot, rvol, real_state, distance)
    print("  Breakout Checklist:")
    print(f"    Pivot crossed?          {'YES' if checklist['pivot_crossed'] else 'NO'}")
    print(f"    Breakout volume RVOL    {checklist['breakout_rvol']}x")
    vol_20d = checklist['volume_vs_20d_avg']
    print(f"    Volume vs 20d avg       {vol_20d}x" if vol_20d is not None else "    Volume vs 20d avg       N/A (insufficient history)")
    print(f"    Close above pivot?      {'YES' if checklist['close_above_pivot'] else 'NO'}")
    print(f"    % above pivot           {checklist['pct_above_pivot']:+.2f}%")
    print(f"    Days above pivot        {checklist['days_above_pivot']}")
    print(f"    Retest successful?      {'YES' if checklist['retest_successful'] else 'NO'}")


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

    # #62 - VCR directional interpretation, combining VCR with what's
    # already computed (distance to pivot, RS trend, current state) -
    # a bare VCR number alone doesn't say whether tightening is
    # constructive or a warning sign, per real, direct feedback.
    if vcr is not None and vcr < 1.0:
        if real_state == "STOP_BREACHED":
            directional_note = "CONTRACTING AFTER A FAILED BREAKOUT - possibly bearish, the stop was already hit once"
        elif rs_drawdown is not None and rs_drawdown <= -20:
            directional_note = "CONTRACTING WHILE RELATIVE STRENGTH DETERIORATES - potentially dangerous, not a clean setup"
        elif distance < 0:
            directional_note = "CONTRACTING INTO RESISTANCE - constructive, genuinely tightening as it approaches the pivot"
        else:
            directional_note = "CONTRACTING ABOVE PIVOT - already through resistance, watch for continuation vs stalling"
        print(f"  VCR Interpretation: {directional_note}")

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

    fib_zone = compute_fibonacci_value_zone(ticker)
    if fib_zone:
        print()
        print(f"  Value Zone (Fibonacci 61.8%): {fib_zone['signal']} - zone {fib_zone['fib_zone']}, "
              f"stop {fib_zone['stop_loss']}, target {fib_zone['target']}")

    if fundamentals:
        print()
        print("  Value Zone (Fundamentals, 4 dimensions - fetches sector peers, adds real latency):")
        value_zone = compute_value_zone(ticker, fundamentals)
        if value_zone:
            for dimension, verdict in value_zone.items():
                if verdict:
                    print(f"    {dimension}: {verdict}")

    print(f"  Market Regime    : {regime}  (exposure {int(multiplier*100)}%)")

    if capital is not None and risk_pct is not None and risk > 0:

        risk_amt = capital * (risk_pct / 100)
        size_factor = get_size_factor(atr_pct)
        qty_by_risk = int((risk_amt * size_factor) / risk)

        # Real, serious gap found and fixed: this had NO concentration
        # cap at all. When the stop is tight (small risk per share),
        # the risk-budget formula alone can suggest a position size that
        # consumes a huge, unsafe share of total capital - confirmed
        # directly: it suggested 48% of capital on one trade with a
        # genuinely tight stop. Applying the same 20% cap already
        # established and used in Risk_Positioning_Engine.py.
        CONCENTRATION_CAP_PCT = 0.20
        max_shares_by_concentration = int((capital * CONCENTRATION_CAP_PCT) / price) if price > 0 else 0

        qty = min(qty_by_risk, max_shares_by_concentration)
        capital_used = round(qty * price, 2)
        capital_pct = round((capital_used / capital) * 100, 1) if capital > 0 else 0

        print("-" * 68)
        print(f"  Suggested Qty    : {qty} shares  (Rs{capital_used:,.0f} used, {capital_pct}% of capital)")

        if qty_by_risk > max_shares_by_concentration:
            print(f"    -> Capped at {int(CONCENTRATION_CAP_PCT*100)}% concentration limit "
                  f"(risk-based sizing alone would have suggested {qty_by_risk} shares - "
                  f"the stop is tight enough that the risk budget alone doesn't limit position size)")

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