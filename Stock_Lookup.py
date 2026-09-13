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


def compute_undercut_reclaim(ticker, support_lookback=30, recent_window=5, min_volume_ratio=1.3):
    """
    #81 - Real, direct feedback: "undercut and reclaim scenarios" -
    genuinely absent before this. A real, specific pattern: price
    briefly trades BELOW an already-established support level
    (trapping shorts and weak-handed longs into selling at the worst
    moment), then reclaims it - often triggering a sharp move higher
    as those trapped shorts cover. Different from
    Reversal_Exhaustion_Scanner.py's capitulation logic, which looks
    for the single lowest close in a window, not a specific,
    previously-respected support LEVEL being undercut and reclaimed.

    Real, testable definition:
    1. Support level = the lowest LOW in support_lookback days,
       BEFORE the recent_window (a real, already-respected level, not
       an invented one).
    2. Undercut = within recent_window, price traded below that level
       intraday at least once.
    3. Reclaim = the most recent close is back above that level.
    4. Volume confirmation (real, not required, but a genuine quality
       signal) = the reclaim day's volume is at least min_volume_ratio
       times the recent_window's own average volume.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close", "low", "volume"]).sort_values("date").reset_index(drop=True)

        if len(df) < support_lookback + recent_window:
            return None

        support_window = df.iloc[-(support_lookback + recent_window):-recent_window]
        recent = df.tail(recent_window)

        if support_window.empty:
            return None

        support_level = float(support_window["low"].min())

        if support_level <= 0:
            return {"pattern_present": False, "reason": "Invalid support level."}

        undercut_occurred = bool((recent["low"] < support_level).any())

        if not undercut_occurred:
            return {"pattern_present": False, "reason": "No undercut of the established support level detected."}

        current_close = float(recent["close"].iloc[-1])
        reclaimed = current_close > support_level

        if not reclaimed:
            return {
                "pattern_present": False,
                "reason": f"Undercut support (Rs{support_level:.2f}) but hasn't reclaimed it yet - "
                          f"still below, watch for a real reclaim before treating this as bullish.",
                "support_level": round(support_level, 2),
            }

        current_volume = float(recent["volume"].iloc[-1])
        avg_recent_volume = float(recent["volume"].mean())
        volume_confirmed = avg_recent_volume > 0 and (current_volume / avg_recent_volume) >= min_volume_ratio

        return {
            "pattern_present": True,
            "support_level": round(support_level, 2),
            "current_close": round(current_close, 2),
            "volume_confirmed": volume_confirmed,
            "reason": f"Undercut support (Rs{support_level:.2f}) and reclaimed it, "
                      f"now at Rs{current_close:.2f}"
                      + (" - with real volume confirmation" if volume_confirmed
                         else " - reclaim not yet volume-confirmed"),
        }

    except Exception:
        return None


def compute_topping_risk(ticker, prior_lookback=120, recent_window=20,
                          min_prior_gain_pct=25.0, max_recent_net_move_pct=5.0,
                          min_distribution_days=3):
    """
    #80 - Real, direct feedback: Stage Analysis (Weinstein) - Stage 1
    (basing) and Stage 2 (advancing) are already effectively captured
    by this system's BASE_BUILDING/VALID_BREAKOUT states. Stage 3
    (topping/distribution) is genuinely absent - the same blind spot
    Reversal_Exhaustion_Scanner.py addressed for the opposite
    direction (a stock reversing OUT of a downtrend). This detects a
    PREVIOUSLY STRONG stock now churning near its highs with
    genuine, repeated distribution-day selling pressure - not a
    scoring factor (a high topping score should reduce conviction,
    not increase it), a direct warning check instead.

    Real, testable definition:
    1. Genuine prior strength: at least min_prior_gain_pct gain from
       the start of prior_lookback to its peak within that window -
       confirms real Stage 2 history, not just noise.
    2. Currently churning: price is still near that peak (within 10%)
       but recent_window's net return is small - no further real
       progress despite being at/near highs.
    3. Real, repeated distribution-day selling pressure within the
       recent window (same down-day-on-higher-volume formula as
       Market_Regime_Engine.py's check_distribution_day(), applied
       per-stock) - at least min_distribution_days, not just one.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close", "volume"]).sort_values("date").reset_index(drop=True)

        if len(df) < prior_lookback + recent_window:
            return None

        prior_window = df.iloc[-(prior_lookback + recent_window):-recent_window]
        recent = df.tail(recent_window)

        if prior_window.empty:
            return None

        prior_start = float(prior_window["close"].iloc[0])
        prior_peak = float(prior_window["close"].max())

        if prior_start <= 0:
            return None

        prior_gain_pct = (prior_peak - prior_start) / prior_start * 100

        if prior_gain_pct < min_prior_gain_pct:
            return {"topping_risk": False, "reason": "No genuine prior Stage 2 strength found."}

        recent_start = float(recent["close"].iloc[0])
        recent_end = float(recent["close"].iloc[-1])
        recent_net_move_pct = (recent_end - recent_start) / recent_start * 100 if recent_start > 0 else 0

        near_peak = recent_end >= prior_peak * 0.90

        if not near_peak or abs(recent_net_move_pct) > max_recent_net_move_pct:
            return {"topping_risk": False, "reason": "Not currently churning near prior highs."}

        closes = recent["close"].values
        volumes = recent["volume"].values
        distribution_days = sum(
            1 for i in range(1, len(closes))
            if closes[i] < closes[i - 1] and volumes[i] > volumes[i - 1]
        )

        topping_risk = distribution_days >= min_distribution_days

        return {
            "topping_risk": topping_risk,
            "prior_gain_pct": round(prior_gain_pct, 2),
            "recent_net_move_pct": round(recent_net_move_pct, 2),
            "distribution_days": distribution_days,
            "reason": f"+{prior_gain_pct:.1f}% prior rally, now churning "
                      f"({recent_net_move_pct:+.1f}% over {recent_window}d) with "
                      f"{distribution_days} distribution days"
                      + (" - genuine Stage 3 topping risk" if topping_risk else ""),
        }

    except Exception:
        return None


def compute_higher_lows(ticker, lookback=50, swing_window=3, min_swings=2, min_prominence_pct=2.0):
    """
    #87 - Real, direct feedback: "building higher lows while a stock
    rides a moving average" - genuinely absent before this. Detects
    real, local swing lows (a day whose low is the minimum among
    swing_window days before and after it) within a recent lookback,
    then checks whether that sequence is genuinely, monotonically
    increasing.

    Real bug caught in testing: a plain local-minimum definition picks
    up every noise-level dip, not just genuinely significant
    retracements - confirmed directly when realistic (noisy) test data
    produced 6 "swing lows" instead of the 3 intended, real ones.
    Fixed with a minimum prominence filter (a swing low must be at
    least min_prominence_pct below the highest point since the prior
    swing low) - filters out noise, keeps genuine pullbacks.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["low", "high"]).sort_values("date").reset_index(drop=True)

        if len(df) < lookback:
            return None

        window = df.tail(lookback).reset_index(drop=True)
        lows = window["low"].values
        highs = window["high"].values

        raw_swing_lows = []
        for i in range(swing_window, len(lows) - swing_window):
            neighborhood = lows[i - swing_window:i + swing_window + 1]
            if lows[i] == neighborhood.min():
                raw_swing_lows.append((i, float(lows[i])))

        # Real prominence filter: only keep a swing low if it's
        # genuinely, meaningfully below the highest point since the
        # LAST ACCEPTED swing low - filters out noise-level dips.
        # Real bug caught and fixed in testing: an earlier version
        # carried a cumulative peak across the whole window, never
        # resetting after accepting a swing low, so later candidates
        # were compared against a stale, distant peak rather than the
        # real, local one - making genuinely small dips look falsely
        # significant.
        significant_swings = []
        last_accepted_idx = 0

        for idx, val in raw_swing_lows:
            peak_since_last = float(highs[last_accepted_idx:idx + 1].max())
            if peak_since_last <= 0:
                continue
            drop_pct = (peak_since_last - val) / peak_since_last * 100
            if drop_pct >= min_prominence_pct:
                significant_swings.append((idx, val))
                last_accepted_idx = idx

        if len(significant_swings) < min_swings:
            return {"pattern_present": False, "swing_count": len(significant_swings)}

        values = [v for _, v in significant_swings]
        is_higher_lows = all(values[i] < values[i + 1] for i in range(len(values) - 1))

        return {
            "pattern_present": is_higher_lows,
            "swing_count": len(significant_swings),
            "swing_lows": values,
        }

    except Exception:
        return None


def compute_ema_crossback(ticker, ema_span=20, lookback=10):
    """
    #83 (part 1) - Real, direct feedback: "EMA crossbacks" - genuinely
    absent before this. Price briefly dips below a key EMA, then
    quickly closes back above it - a real "test and hold" continuation
    signal, meaningfully different from undercut-and-reclaim (#81),
    which checks a specific, previously-established support LEVEL, not
    a moving, dynamic EMA line.

    Real, testable definition - all required:
    1. The EMA itself must be genuinely rising (ema[-1] > ema[-lookback])
       - without this, a dip-and-recovery in a flat/declining EMA isn't
       a meaningful bullish continuation signal, just noise.
    2. Close traded below the EMA at least once within the lookback.
    3. The most recent close is back above the EMA.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

        if len(df) < ema_span + lookback:
            return None

        ema = df["close"].ewm(span=ema_span, adjust=False).mean()

        ema_rising = bool(ema.iloc[-1] > ema.iloc[-lookback])

        if not ema_rising:
            return {"pattern_present": False, "reason": f"EMA{ema_span} isn't genuinely rising - not a meaningful uptrend context."}

        recent_close = df["close"].tail(lookback).values
        recent_ema = ema.tail(lookback).values

        dipped_below = bool((recent_close[:-1] < recent_ema[:-1]).any())

        if not dipped_below:
            return {"pattern_present": False, "reason": f"Price hasn't dipped below EMA{ema_span} recently - no crossback to detect."}

        current_close = float(recent_close[-1])
        current_ema = float(recent_ema[-1])
        reclaimed = current_close > current_ema

        return {
            "pattern_present": reclaimed,
            "ema_span": ema_span,
            "current_close": round(current_close, 2),
            "current_ema": round(current_ema, 2),
            "reason": f"Dipped below EMA{ema_span} (Rs{current_ema:.2f}) recently and reclaimed it, "
                      f"now at Rs{current_close:.2f} - genuine continuation signal within a rising trend"
                      if reclaimed else
                      f"Dipped below EMA{ema_span} (Rs{current_ema:.2f}) but hasn't reclaimed it yet - "
                      f"still below, watch before treating this as a continuation signal.",
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

        # #86 - real, direct feedback: binary rising/falling loses the
        # distinction between a barely-positive slope and a genuinely
        # steep one - the video methodology explicitly wants "~45
        # degrees or steeper" as an ideal trend quality signal, not
        # just "up vs down". A raw price slope is scale-dependent
        # (different stocks have wildly different price levels), so
        # this converts average daily % change to an angle via
        # arctan(), a standard, defensible way to make it comparable
        # across stocks - honestly, this is a NORMALIZED angle
        # convention (1%/day average EMA gain -> 45 degrees), not a
        # literal, pixel-accurate chart angle, which would depend on
        # each chart's own aspect ratio and isn't a fixed, comparable
        # number at all.
        import math

        lookback = 10
        ema20_pct_change_per_day = ((ema20.iloc[-1] / ema20.iloc[-lookback]) - 1) / lookback
        ema20_angle_degrees = round(math.degrees(math.atan(ema20_pct_change_per_day * 100)), 1)

        return {
            "ema20_rising": ema20_rising,
            "ema50_rising": ema50_rising,
            "note": note,
            "ema20_angle_degrees": ema20_angle_degrees,
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


def compute_adr(ticker, lookback=20):
    """
    #79 - Real, direct feedback: "high Average Daily Range (ADR) stocks
    preferred; low-ADR/thin stocks discouraged" - genuinely absent
    before this. Distinct from compute_vcr()'s RELATIVE contraction
    ratio (recent range vs historical range) - this is the standard,
    ABSOLUTE ADR% used as a selection filter: how much a stock
    typically moves intraday, as a percentage, not a ratio.

    Standard formula: average of (High-Low)/Low per day, over the
    lookback window, as a percentage.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["high", "low"]).sort_values("date")

        if len(df) < lookback:
            return None

        recent = df.tail(lookback)
        daily_ranges_pct = (recent["high"] - recent["low"]) / recent["low"] * 100
        adr_pct = round(float(daily_ranges_pct.mean()), 2)

        return {"adr_pct": adr_pct}

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


def compute_breakout_phase_volume(ticker, real_state, days_above_pivot, rvol, weekly_rvol):
    """
    #68 - Real, direct feedback: showing "Weekly RVOL: 0.22x" without
    phase context can misread a genuinely normal pre-breakout coil as
    a concerning weak-volume signal. Low weekly volume is EXPECTED
    before a breakout (contracting volatility, quiet accumulation) -
    what actually matters is intraday RVOL at the moment of breakout,
    and whether volume stays elevated afterward, not before it.

    Reuses real_state (Execution_State_Machine.py's actual states) and
    days_above_pivot (#65's checklist) rather than inventing a new
    phase classification.
    """

    PRE_BREAKOUT_STATES = ("APPROACHING", "BASE_BUILDING", "TESTING")
    AT_BREAKOUT_STATES = ("VALID_BREAKOUT", "RETEST_SUCCESS")

    if real_state in PRE_BREAKOUT_STATES:
        return {
            "phase": "PRE-BREAKOUT",
            "metric_label": "Weekly RVOL",
            "metric_value": weekly_rvol,
            "note": "Low/contracting volume is NORMAL here - this is what a real pre-breakout coil looks like",
        }

    if real_state in AT_BREAKOUT_STATES:
        meets_threshold = rvol is not None and rvol >= 1.5
        return {
            "phase": "AT BREAKOUT",
            "metric_label": "Breakout RVOL",
            "metric_value": rvol,
            "note": "Meets the real >=1.5x confirmation threshold" if meets_threshold
                    else "Below the real >=1.5x confirmation threshold - a genuinely weaker breakout",
        }

    if days_above_pivot >= 2:
        # Post-breakout, holding - check whether volume has genuinely
        # STAYED elevated recently, not just whether the whole
        # post-breakout window's average looks elevated (which a
        # single initial spike could dominate, masking a real fade
        # afterward - caught directly in testing before this reached
        # you).
        import os
        import pandas as pd
        from core.config import PARQUET_CACHE_DIR

        path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

        if os.path.exists(path):
            try:
                df = pd.read_parquet(path)
                df.columns = [str(c).lower() for c in df.columns]
                df = df.dropna(subset=["volume"]).sort_values("date")

                recent_window = min(3, days_above_pivot - 1)  # exclude the initial breakout day itself

                if recent_window >= 1 and len(df) >= days_above_pivot + 20:
                    recent_avg = float(df["volume"].tail(recent_window).mean())
                    pre_breakout_avg = float(df["volume"].iloc[-(days_above_pivot + 20):-days_above_pivot].mean())

                    if pre_breakout_avg > 0:
                        ratio = round(recent_avg / pre_breakout_avg, 2)
                        return {
                            "phase": "POST-BREAKOUT",
                            "metric_label": "Post-Breakout Volume",
                            "metric_value": ratio,
                            "note": "Volume genuinely remaining elevated since breakout" if ratio >= 1.0
                                    else "Volume fading since the breakout - a real warning sign",
                        }
            except Exception:
                pass

    return {
        "phase": "OTHER",
        "metric_label": "Weekly RVOL",
        "metric_value": weekly_rvol,
        "note": None,
    }


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


def compute_sector_strength_context(ticker):
    """
    Real, direct integration fix: Sector_Strength_Ranker.py existed as
    a standalone, manually-run script with no persistence and no
    connection to live decision-making. Now reads the latest saved
    ranking to show whether this specific stock's sector is currently
    one of the market's leading or lagging sectors - directly
    addresses the "ride the hot sector" theme-momentum concept, which
    was genuinely absent from live monitoring before this.
    """

    import sqlite3
    from core.config import DB_PATH
    from core.sector_map import get_sector

    sector = get_sector(ticker)

    if sector == "UNKNOWN":
        return None

    try:
        conn = sqlite3.connect(DB_PATH)

        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sector_strength_ranking'"
        ).fetchone()

        if not table_exists:
            conn.close()
            return None

        latest_date = conn.execute("SELECT MAX(run_date) FROM sector_strength_ranking").fetchone()[0]

        if not latest_date:
            conn.close()
            return None

        all_sectors = pd.read_sql(
            "SELECT sector, liquidity_weighted_rs, stock_count FROM sector_strength_ranking "
            "WHERE run_date = ? ORDER BY liquidity_weighted_rs DESC",
            conn, params=(latest_date,)
        )
        conn.close()

        if all_sectors.empty or sector not in all_sectors["sector"].values:
            return None

        rank = int(all_sectors[all_sectors["sector"] == sector].index[0]) + 1
        total = len(all_sectors)
        row = all_sectors[all_sectors["sector"] == sector].iloc[0]

        return {
            "sector": sector,
            "rank": rank,
            "total_sectors": total,
            "rs_score": round(float(row["liquidity_weighted_rs"]), 2),
            "stock_count": int(row["stock_count"]),
            "run_date": latest_date,
        }

    except Exception:
        return None


def compute_relative_performance(ticker, benchmark_ticker="NIFTYBEES", horizons=(20, 63, 126, 252)):
    """
    Real, direct fix for the most important gap identified in the RS
    critique: RS Line Drawdown measures deterioration from a recent
    peak, not current leadership - a stock with +15% relative return
    and -20% drawdown is a stronger leader than one with -5% relative
    return and -2% drawdown, but drawdown alone can't tell them apart.
    This computes actual relative TOTAL RETURN over multiple real
    horizons, so leadership and deterioration are reported as two
    genuinely separate things, not one number standing in for both.

    Uses NIFTYBEES specifically for now (confirmed 498 real trading
    days - enough for all four horizons including the full 252-day
    one). A real Nifty Bank-equivalent sector benchmark is a separate,
    deferred prerequisite (BANKBEES currently has only 43 real days,
    nowhere near enough) - this function accepts a benchmark_ticker
    parameter specifically so it can be reused for that once ready,
    without a second implementation.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")
    bench_path = os.path.join(PARQUET_CACHE_DIR, f"{benchmark_ticker}.parquet")

    if not os.path.exists(path) or not os.path.exists(bench_path):
        return None

    try:
        stock_df = pd.read_parquet(path)
        stock_df.columns = [str(c).lower() for c in stock_df.columns]
        stock_df = stock_df.sort_values("date").set_index("date")

        bench_df = pd.read_parquet(bench_path)
        bench_df.columns = [str(c).lower() for c in bench_df.columns]
        bench_df = bench_df.sort_values("date").set_index("date")

        aligned = pd.DataFrame({
            "stock": stock_df["close"],
            "benchmark": bench_df["close"],
        }).dropna()

        results = {}

        for h in horizons:
            if len(aligned) < h + 1:
                results[h] = None
                continue

            stock_now = float(aligned["stock"].iloc[-1])
            stock_then = float(aligned["stock"].iloc[-(h + 1)])
            bench_now = float(aligned["benchmark"].iloc[-1])
            bench_then = float(aligned["benchmark"].iloc[-(h + 1)])

            if stock_then <= 0 or bench_then <= 0:
                results[h] = None
                continue

            stock_return = (stock_now - stock_then) / stock_then
            bench_return = (bench_now - bench_then) / bench_then
            relative_return = (stock_return - bench_return) * 100

            results[h] = round(relative_return, 2)

        return results

    except Exception:
        return None


def is_banking_stock(ticker):
    """
    Real, honest finding: core/sector_map.py's sector labels are
    inconsistent across data sources - AXISBANK/HDFCBANK are labeled
    "Banking", but RBLBANK (used as this system's own running example
    all night) is labeled "Financial Services" with theme "Banks -
    Regional". A strict sector-name match would have silently excluded
    it. Checking both sector and theme for "bank" catches both cases.
    """

    from core.sector_map import UNIVERSE

    clean = ticker.upper().strip()
    if not clean.endswith(".NS"):
        clean += ".NS"

    entry = UNIVERSE.get(clean)

    if not entry:
        return False

    combined = f"{entry.get('sector', '')} {entry.get('theme', '')}".lower()
    return "bank" in combined


def compute_rs_vs_sector(ticker, lookback=252):
    """
    #67 - RS relative to the stock's own sector, not just NIFTY. Real,
    direct feedback: "a stock can outperform the market while
    underperforming its own sector" - RBLBANK-style setups need both
    views, since they answer genuinely different questions.

    Builds a synthetic, equal-weighted sector benchmark from real peer
    price data (via find_sector_peers(), already built for #66) rather
    than assuming a real sector index file exists in parquet_cache,
    which couldn't be confirmed. Same real "consistency of leadership"
    drawdown methodology as compute_rs_line_drawdown(), just measured
    against sector peers instead of NIFTYBEES.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    peers = find_sector_peers(ticker, max_peers=5)

    if not peers:
        return None

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        stock_df = pd.read_parquet(path).sort_values("date").set_index("date")
        stock_close = stock_df["close"]

        peer_returns = []

        for peer in peers:
            peer_path = os.path.join(PARQUET_CACHE_DIR, f"{peer.upper()}.parquet")
            if not os.path.exists(peer_path):
                continue
            try:
                peer_df = pd.read_parquet(peer_path).sort_values("date").set_index("date")
                # Normalize to a common starting value so each peer
                # contributes an equal-weighted RETURN, not raw price
                # (peers can have vastly different absolute prices)
                normalized = peer_df["close"] / peer_df["close"].iloc[0]
                peer_returns.append(normalized)
            except Exception:
                continue

        if len(peer_returns) < 2:
            return None  # too few real peers for a meaningful synthetic benchmark

        # Real fix, per direct feedback: median instead of mean. A
        # single outlier peer (e.g., one stock crashing or spiking)
        # would drag an equal-weight MEAN in a way that misrepresents
        # "the typical peer" - median is a genuinely better diagnostic
        # for this specific use, even though it's not how a real,
        # tradable index would be constructed.
        sector_index = pd.concat(peer_returns, axis=1).median(axis=1).dropna()

        aligned = pd.DataFrame({
            "stock": stock_close,
            "sector": sector_index,
        }).dropna()

        if len(aligned) < lookback:
            return None

        rs_line = (aligned["stock"] / aligned["stock"].iloc[0]) / (aligned["sector"] / aligned["sector"].iloc[0])
        rs_line = rs_line.tail(lookback)
        drawdown = (rs_line / rs_line.cummax() - 1).min()

        return {
            "drawdown_pct": round(float(drawdown) * 100, 2),
            "peer_count": len(peer_returns),
        }

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


def compute_execution_risk(ticker, qty):
    """
    #74 - Real, direct feedback: "entry -> stop = known risk" ignores
    real execution mechanics. Also directly closes the long-pending
    "order-size-vs-ADV liquidity check" item from the original
    OMS-spine investigation - same underlying need.

    Liquidity (% of ADV) and gap risk (real historical overnight-gap
    distribution) use genuine parquet_cache data, no invented numbers.
    Slippage is HONESTLY labeled as a rough estimate, not an
    empirically calibrated model - no real historical fill data exists
    to calibrate a coefficient against, and presenting one with false
    precision would be worse than not providing it.
    """

    import os
    from core.config import PARQUET_CACHE_DIR

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df = df.dropna(subset=["close", "open", "volume"]).sort_values("date")

        if len(df) < 25:
            return None

        adv_20d = float(df["volume"].tail(20).mean())
        pct_of_adv = round((qty / adv_20d) * 100, 3) if adv_20d > 0 else None

        # Real historical overnight gap distribution - genuine data,
        # not assumed
        gaps = []
        closes = df["close"].tolist()
        opens = df["open"].tolist()
        for i in range(1, min(len(df), 90)):
            prev_close = closes[-(i + 1)]
            today_open = opens[-i]
            if prev_close > 0:
                gaps.append((today_open - prev_close) / prev_close)

        gap_std_pct = round(pd.Series(gaps).std() * 100, 2) if len(gaps) >= 20 else None

        # Honest, clearly-labeled rough estimate - standard square-root
        # market-impact SHAPE (impact scales with the stock's own real
        # volatility and the square root of order size relative to
        # liquidity). Coefficient (0.3) is a reasonable, conservative
        # heuristic, NOT calibrated against real fill data, since none
        # exists.
        slippage_estimate_pct = None
        if pct_of_adv is not None and pct_of_adv > 0:
            daily_returns = df["close"].pct_change().dropna().tail(60)
            daily_vol_pct = float(daily_returns.std()) * 100 if len(daily_returns) >= 20 else None
            if daily_vol_pct is not None:
                slippage_estimate_pct = round(0.3 * daily_vol_pct * (pct_of_adv / 100) ** 0.5, 3)

        return {
            "adv_20d": int(adv_20d),
            "pct_of_adv": pct_of_adv,
            "gap_risk_std_pct": gap_std_pct,
            "slippage_estimate_pct": slippage_estimate_pct,
        }

    except Exception:
        return None


def compute_anticipation_setup(ticker, vcr, distance):
    """
    #82 - Real, direct feedback: "anticipation setups" - genuinely
    absent before this. Positioning ahead of a KNOWN, upcoming
    catalyst, rather than waiting for confirmation - the deliberate
    flip side of #75's event-risk WARNING framing. Combines existing,
    already-computed infrastructure rather than duplicating any of it:
    VCR (genuine contraction), distance-to-pivot (genuine readiness,
    not extended), and compute_event_risk()'s real earnings date.

    Real, testable definition - all three required:
    1. Genuinely tight (VCR < 1.0, the same threshold already used for
       "mildly contracting" elsewhere).
    2. Genuinely near the pivot (-5% to +2% - approaching or just at
       it, not far away or already extended).
    3. A real, known catalyst (earnings) within a reasonable window
       (1-10 days) - reuses compute_event_risk() directly, not a
       second earnings-date lookup.
    """

    if vcr is None or distance is None:
        return None

    is_tight = vcr < 1.0
    is_near_pivot = -5.0 <= distance <= 2.0

    if not (is_tight and is_near_pivot):
        return {"setup_present": False, "reason": "Not tight and near the pivot simultaneously."}

    event_risk = compute_event_risk(ticker)

    if not event_risk or event_risk.get("days_to_earnings") is None:
        return {"setup_present": False, "reason": "No known upcoming catalyst to anticipate."}

    days_to_earnings = event_risk["days_to_earnings"]

    if not (1 <= days_to_earnings <= 10):
        return {
            "setup_present": False,
            "reason": f"Tight and near pivot, but earnings is {days_to_earnings} days away - "
                      f"outside the real anticipation window (1-10 days).",
        }

    return {
        "setup_present": True,
        "vcr": vcr,
        "distance": distance,
        "days_to_earnings": days_to_earnings,
        "reason": f"Genuinely tight (VCR {vcr}) and near pivot ({distance:+.1f}%), with earnings "
                  f"in {days_to_earnings} days - a real anticipation setup, deliberately higher-risk "
                  f"since the catalyst could trigger a move either direction.",
    }


def compute_event_risk(ticker):
    """
    #75 - Real, direct feedback: "a technical breakout immediately
    before earnings is a fundamentally different risk profile from
    one occurring in an ordinary session." Confirmed directly via
    investigation: yfinance's .calendar genuinely provides a real
    upcoming earnings date for Indian stocks (not assumed to work),
    plus ex-dividend date. Historical earnings dates (.earnings_dates)
    failed due to a missing lxml package, not a data-availability
    issue - not chased further since .calendar already gives the more
    critical piece (the upcoming date) for this specific use case.
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        from datetime import date

        normalized = normalize_ticker(ticker)
        yf_ticker = yf.Ticker(f"{normalized}.NS")
        calendar = yf_ticker.calendar

        if not calendar:
            return None

        result = {"earnings_date": None, "days_to_earnings": None, "ex_dividend_date": None}

        earnings_dates = calendar.get("Earnings Date")
        if earnings_dates and len(earnings_dates) > 0:
            next_earnings = earnings_dates[0]
            result["earnings_date"] = next_earnings.strftime("%Y-%m-%d")
            result["days_to_earnings"] = (next_earnings - date.today()).days

        ex_div = calendar.get("Ex-Dividend Date")
        if ex_div:
            result["ex_dividend_date"] = ex_div.strftime("%Y-%m-%d")

        return result

    except Exception:
        return None


def compute_financial_health_extended(ticker):
    """
    Real, direct investigation confirmed: currentRatio, EBIT are
    genuinely None for RBLBANK (a bank - no traditional current-assets
    or EBIT structure) but genuinely present for TCS (a non-bank:
    currentRatio=2.276, quickRatio=2.045). This is sector-dependent,
    not a bug - each field is checked and gracefully omitted when
    genuinely absent, never fabricated or defaulted to a misleading
    number.

    Interest Coverage and ROCE use Pretax Income + Interest Expense as
    an EBIT approximation, since direct EBIT is unavailable even for
    non-bank stocks (confirmed via investigation) - both from
    .financials' confirmed real lines. ROCE also needs "Invested
    Capital" from .balance_sheet, also confirmed present.
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        normalized = normalize_ticker(ticker)
        yf_ticker = yf.Ticker(f"{normalized}.NS")

        result = {
            "current_ratio": None,
            "ebitda_margin": None,
            "interest_coverage": None,
            "roce": None,
        }

        info = yf_ticker.info
        result["current_ratio"] = info.get("currentRatio")

        financials = yf_ticker.financials
        if financials is not None and not financials.empty:

            if "EBITDA" in financials.index and "Total Revenue" in financials.index:
                ebitda = financials.loc["EBITDA"].dropna()
                revenue = financials.loc["Total Revenue"].dropna()
                if len(ebitda) > 0 and len(revenue) > 0 and revenue.iloc[0] > 0:
                    result["ebitda_margin"] = round((ebitda.iloc[0] / revenue.iloc[0]) * 100, 2)

            if "Pretax Income" in financials.index and "Interest Expense" in financials.index:
                pretax = financials.loc["Pretax Income"].dropna()
                interest_exp = financials.loc["Interest Expense"].dropna()
                if len(pretax) > 0 and len(interest_exp) > 0 and interest_exp.iloc[0] > 0:
                    ebit_approx = pretax.iloc[0] + interest_exp.iloc[0]
                    result["interest_coverage"] = round(ebit_approx / interest_exp.iloc[0], 2)

                    balance_sheet = yf_ticker.balance_sheet
                    if balance_sheet is not None and not balance_sheet.empty and "Invested Capital" in balance_sheet.index:
                        invested_capital = balance_sheet.loc["Invested Capital"].dropna()
                        if len(invested_capital) > 0 and invested_capital.iloc[0] > 0:
                            result["roce"] = round((ebit_approx / invested_capital.iloc[0]) * 100, 2)

        return result

    except Exception:
        return None


def compute_debt_to_equity_trend(ticker, years=5):
    """
    Real D/E TREND across 5 years, not just the single current value
    already available via .info's debtToEquity. Uses .balance_sheet's
    confirmed real "Total Debt" and "Stockholders Equity" lines.
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        normalized = normalize_ticker(ticker)
        yf_ticker = yf.Ticker(f"{normalized}.NS")
        balance_sheet = yf_ticker.balance_sheet

        if balance_sheet is None or balance_sheet.empty:
            return None
        if "Total Debt" not in balance_sheet.index or "Stockholders Equity" not in balance_sheet.index:
            return None

        debt = balance_sheet.loc["Total Debt"]
        equity = balance_sheet.loc["Stockholders Equity"]

        result = []
        for date in debt.index[:years]:
            d, e = debt.get(date), equity.get(date)
            if d is not None and e is not None and e > 0:
                result.append((date.strftime("%Y-%m-%d"), round(float(d) / float(e), 2)))

        return result if result else None

    except Exception:
        return None


def compute_free_cash_flow_history(ticker, years=5):
    """
    Real FCF, using yfinance's own already-computed "Free Cash Flow"
    line from .cashflow - confirmed directly present via investigation,
    not derived manually from operating cash flow minus capex (which
    would risk a different definition than yfinance's own).
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        normalized = normalize_ticker(ticker)
        yf_ticker = yf.Ticker(f"{normalized}.NS")
        cashflow = yf_ticker.cashflow

        if cashflow is None or cashflow.empty or "Free Cash Flow" not in cashflow.index:
            return None

        fcf_series = cashflow.loc["Free Cash Flow"].dropna()
        fcf_series = fcf_series[fcf_series.index.sort_values(ascending=False)][:years]

        return [(date.strftime("%Y-%m-%d"), round(float(val), 2))
                for date, val in fcf_series.items()]

    except Exception:
        return None


def compute_growth_cagr(ticker):
    """
    Real Revenue/Net Profit/EPS CAGR, confirmed buildable via direct
    investigation of yfinance's .financials for a real Indian stock
    (RBLBANK) - "Total Revenue", "Net Income", and "Diluted EPS" lines
    are genuinely present, 5 real annual columns, most recent first.
    Not assumed to work - verified with real data before building this.
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        normalized = normalize_ticker(ticker)
        yf_ticker = yf.Ticker(f"{normalized}.NS")
        financials = yf_ticker.financials

        if financials is None or financials.empty:
            return None

        # Columns come back most-recent-first (confirmed directly) -
        # reverse to oldest-first for a clean, readable CAGR calculation
        financials = financials[financials.columns[::-1]]

        def cagr(series, years):
            if len(series) <= years:
                return None
            end_val = series.iloc[-1]
            start_val = series.iloc[-(years + 1)]
            if start_val is None or end_val is None or start_val <= 0:
                return None
            try:
                return round((((end_val / start_val) ** (1 / years)) - 1) * 100, 2)
            except Exception:
                return None

        result = {}

        for label, line_item in [("revenue", "Total Revenue"),
                                  ("net_profit", "Net Income"),
                                  ("eps", "Diluted EPS")]:
            if line_item in financials.index:
                series = financials.loc[line_item].dropna()
                result[f"{label}_cagr_3y"] = cagr(series, 3)
                result[f"{label}_cagr_5y"] = cagr(series, 5)
            else:
                result[f"{label}_cagr_3y"] = None
                result[f"{label}_cagr_5y"] = None

        return result

    except Exception:
        return None


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
            # Added for the valuation comparison (P/E, P/B, EV/EBITDA vs
            # sector average) - all from this same .info call, zero
            # extra API cost
            "enterprise_value": info.get("enterpriseValue"),
            "ebitda": info.get("ebitda"),
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


def compute_dividend_history(ticker, years=5):
    """
    Real dividend history via yfinance's own .dividends property - a
    genuinely simple, direct data source, not a derived calculation.
    """

    try:
        import yfinance as yf
        from core.symbol_utils import normalize_ticker
    except ImportError:
        return None

    try:
        normalized = normalize_ticker(ticker)
        divs = yf.Ticker(f"{normalized}.NS").dividends

        if divs is None or divs.empty:
            return {"has_dividends": False, "recent": []}

        cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365 * years)
        recent_divs = divs[divs.index >= cutoff]

        return {
            "has_dividends": len(recent_divs) > 0,
            "recent": [(str(d.date()), round(float(amt), 2)) for d, amt in recent_divs.items()],
        }

    except Exception:
        return None


def compute_valuation_comparison(ticker, fundamentals):
    """
    Real, direct extension per Stock_Lookup.py's redefined purpose:
    deeper fundamental/valuation insight, complementing
    Live_Execution_Monitor's technical focus. Current P/E, P/B, and
    EV/EBITDA compared against a real sector-peer average - reuses
    find_sector_peers() and fetch_quick_fundamentals() exactly as-is,
    no new data source.

    HONEST SCOPE: this covers current values and sector average only.
    A genuine "stock's own 5-year historical average" needs historical
    EPS/book-value data, which requires directly testing yfinance's
    historical financials API (.financials/.quarterly_earnings) -
    explicitly NOT assumed to work here, deferred to a separate,
    evidence-based investigation before building on it.
    """

    if not fundamentals:
        return None

    pe = fundamentals.get("trailing_pe")
    pb = fundamentals.get("price_to_book")
    ev = fundamentals.get("enterprise_value")
    ebitda = fundamentals.get("ebitda")
    ev_ebitda = round(ev / ebitda, 2) if ev and ebitda and ebitda > 0 else None

    peers = find_sector_peers(ticker, max_peers=5)
    peer_pes, peer_pbs, peer_ev_ebitdas = [], [], []

    for peer in peers:
        peer_fund = fetch_quick_fundamentals(peer)
        if not peer_fund:
            continue
        if peer_fund.get("trailing_pe"):
            peer_pes.append(peer_fund["trailing_pe"])
        if peer_fund.get("price_to_book"):
            peer_pbs.append(peer_fund["price_to_book"])
        p_ev, p_ebitda = peer_fund.get("enterprise_value"), peer_fund.get("ebitda")
        if p_ev and p_ebitda and p_ebitda > 0:
            peer_ev_ebitdas.append(p_ev / p_ebitda)

    import statistics

    # Real bug fix, per direct feedback: peer_count previously showed
    # the TOTAL peers found (e.g. 5), not how many actually had valid
    # data for each specific metric - misleadingly implied more
    # coverage than the median was actually based on. Now tracks each
    # metric's own real count, since PE/PB/EV-EBITDA availability can
    # genuinely differ per peer (one peer missing PE doesn't mean it's
    # also missing PB).
    return {
        "pe": pe,
        "pe_sector_avg": round(statistics.median(peer_pes), 2) if peer_pes else None,
        "pe_peer_count": len(peer_pes),
        "pb": pb,
        "pb_sector_avg": round(statistics.median(peer_pbs), 2) if peer_pbs else None,
        "pb_peer_count": len(peer_pbs),
        "ev_ebitda": ev_ebitda,
        "ev_ebitda_sector_avg": round(statistics.median(peer_ev_ebitdas), 2) if peer_ev_ebitdas else None,
        "ev_ebitda_peer_count": len(peer_ev_ebitdas),
        "total_peers_available": len(peers),
    }


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
                result["sector_peer"] = f"CHEAPER than sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, {len(peer_pes)} peers with valid PE)"
            elif pe > peer_median_pe * 1.15:
                result["sector_peer"] = f"MORE EXPENSIVE than sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, {len(peer_pes)} peers with valid PE)"
            else:
                result["sector_peer"] = f"IN LINE with sector peers (PE {pe:.1f} vs peer median {peer_median_pe:.1f}, {len(peer_pes)} peers with valid PE)"
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
        distance=distance,
        earnings_gap_strength=factors.get("earnings_gap_strength")
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
    print()
    print("  === TRADING OPPORTUNITY ===")
    print(f"  Conviction Score : {score}/100  (Opportunity {opportunity} / Readiness {readiness})")
    print(f"  Tier             : {tier}")

    if distance < 0:
        edp = calculate_edp(distance, atr_pct)
        if edp:
            print(f"  Expected Days to Pivot : {edp}")

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

    # #68 - phase-aware volume, real fix for a real concern: showing
    # weekly RVOL without context risked misreading a normal
    # pre-breakout coil as a weak-volume warning sign.
    phase_vol = compute_breakout_phase_volume(ticker, real_state, checklist['days_above_pivot'], rvol, weekly_rvol)
    print(f"  Volume Phase     : {phase_vol['phase']}")
    if phase_vol['metric_value'] is not None:
        print(f"  {phase_vol['metric_label']:<17}: {phase_vol['metric_value']}x")
    if phase_vol['note']:
        print(f"    -> {phase_vol['note']}")


    ema50 = compute_ema50(ticker)
    pullback_note = classify_pullback(price, tech.get("ema20"), ema50)
    if pullback_note:
        print(f"  Also             : {pullback_note}")

    slope = compute_ema_slope_persistence(ticker)
    if slope:
        angle = slope.get("ema20_angle_degrees")
        angle_note = ""
        if angle is not None:
            if angle >= 45:
                angle_note = "  (steep, ideal trend angle)"
            elif angle >= 20:
                angle_note = "  (moderate angle)"
            elif angle > 0:
                angle_note = "  (shallow angle)"
        print(f"  EMA Slope        : {slope['note']}")
        if angle is not None:
            print(f"    EMA20 Angle    : {angle:+.1f}°{angle_note}")

    higher_lows = compute_higher_lows(ticker)
    if higher_lows and higher_lows.get("swing_count", 0) >= 2:
        if higher_lows["pattern_present"]:
            lows_str = " -> ".join(f"Rs{v:.2f}" for v in higher_lows["swing_lows"])
            print(f"  Higher Lows      : YES ({higher_lows['swing_count']} swings: {lows_str}) - genuine accumulation pattern")
        else:
            print(f"  Higher Lows      : NO ({higher_lows['swing_count']} swings found, not consistently rising)")

    topping = compute_topping_risk(ticker)
    if topping and topping.get("topping_risk"):
        print(f"  ⚠ TOPPING RISK   : {topping['reason']}")

    undercut = compute_undercut_reclaim(ticker)
    if undercut and undercut.get("pattern_present"):
        print(f"  Undercut/Reclaim : {undercut['reason']}")

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

        adr = compute_adr(ticker)
        if adr:
            adr_pct = adr["adr_pct"]
            if adr_pct >= 4:
                adr_note = "genuinely high ADR - real profit potential per swing"
            elif adr_pct >= 2:
                adr_note = "moderate ADR"
            else:
                adr_note = "low ADR - a thin, low-movement stock, less swing-trade potential"
            print(f"  ADR              : {adr_pct}%  ({adr_note})")

        anticipation = compute_anticipation_setup(ticker, vcr, distance)
        if anticipation and anticipation.get("setup_present"):
            print(f"  🎯 ANTICIPATION  : {anticipation['reason']}")

    ema_crossback = compute_ema_crossback(ticker)
    if ema_crossback and ema_crossback.get("pattern_present"):
        print(f"  EMA Crossback    : {ema_crossback['reason']}")

    rs_drawdown = compute_rs_line_drawdown(ticker)
    # Real, direct fix: relative RETURN and RS drawdown answer genuinely
    # different questions (current leadership vs deterioration from a
    # peak) - shown together now, neither one carrying the whole
    # assessment alone.
    rel_perf = compute_relative_performance(ticker)
    if rel_perf:
        print("  Relative Performance vs NIFTY:")
        for h, label in [(20, "20D"), (63, "63D"), (126, "126D"), (252, "252D")]:
            val = rel_perf.get(h)
            if val is not None:
                print(f"    {label:<6} {val:+.1f}%")

    print()
    print("  === RELATIVE STRENGTH - vs NIFTYBEES ===")

    rel_perf = compute_relative_performance(ticker)
    if rel_perf:
        for h, label in [(20, "20D"), (63, "63D"), (126, "126D"), (252, "252D")]:
            val = rel_perf.get(h)
            if val is not None:
                print(f"    {label} Relative Return  : {val:+.2f}%")
            else:
                print(f"    {label} Relative Return  : unavailable (insufficient history)")

    if rs_drawdown is not None:
        if rs_drawdown > -10:
            drawdown_note = "very persistent relative leadership"
        elif rs_drawdown > -20:
            drawdown_note = "reasonably consistent leadership"
        else:
            drawdown_note = "choppy - relative outperformance has had real setbacks"
        print(f"  RS Line Drawdown     : {rs_drawdown}%  ({drawdown_note})")

    # Real, direct fix: RS Line Drawdown measures distance from a past
    # peak, not current standing - a stock can be genuinely
    # outperforming right now while still well below its own RS peak.
    # Based on the 20D horizon specifically, matching the real example
    # given: "+4.2% over 20 days" is what determines current
    # leadership, not the multi-year drawdown figure.
    if rel_perf and rel_perf.get(20) is not None:
        leadership = "CURRENTLY OUTPERFORMING" if rel_perf[20] > 0 else "CURRENTLY UNDERPERFORMING"
        print(f"  Current Leadership   : {leadership}  (based on 20D relative return)")

    # Phase B of the RS redesign: BANKBEES backfilled to 4,353 real
    # rows (from 2009), confirmed sufficient for all 4 horizons. Only
    # shown for genuine banking stocks - showing "vs BANKBEES" for a
    # non-banking stock would be meaningless. Precisely labeled as an
    # ETF proxy, not "NIFTY BANK INDEX" itself, per real, direct
    # feedback about that distinction.
    if is_banking_stock(ticker):
        print()
        print("  === RELATIVE STRENGTH - vs BANKBEES (sector benchmark proxy) ===")

        sector_perf = compute_relative_performance(ticker, benchmark_ticker="BANKBEES")
        if sector_perf:
            for h, label in [(20, "20D"), (63, "63D"), (126, "126D"), (252, "252D")]:
                val = sector_perf.get(h)
                if val is not None:
                    print(f"    {label} Relative Return  : {val:+.2f}%")
                else:
                    print(f"    {label} Relative Return  : unavailable (insufficient history)")

            if sector_perf.get(20) is not None:
                sector_leadership = "CURRENTLY OUTPERFORMING SECTOR" if sector_perf[20] > 0 else "CURRENTLY UNDERPERFORMING SECTOR"
                print(f"  Sector Leadership    : {sector_leadership}  (based on 20D relative return)")
        else:
            print("    Unable to compute - check BANKBEES data availability")

    rs_sector = compute_rs_vs_sector(ticker)
    if rs_sector:
        sector_dd = rs_sector["drawdown_pct"]
        if sector_dd > -10:
            sector_note = "very persistent leadership among comparable peers"
        elif sector_dd > -20:
            sector_note = "reasonably consistent leadership among comparable peers"
        else:
            sector_note = "choppy - underperforming comparable peers at times"
        # Real, honest relabeling per direct feedback: explicit "RS
        # Peer Basket" framing distinguishes this from the "Valuation
        # Peer Basket" below - both draw from the same
        # find_sector_peers() call, but each metric's actual usable
        # count can genuinely differ (a peer might have valid price
        # history for RS but missing PE data, or vice versa). Without
        # this distinction, seeing "5 peers" here and "n=4" there reads
        # as a discrepancy rather than the legitimate, different thing
        # it actually is.
        print(f"  RS Peer Basket ({rs_sector['peer_count']} peers available)")
        print(f"    Median relative return : {sector_dd}%  ({sector_note})")

        # #67 - the specific case the real feedback called out: a stock
        # can outperform the market while underperforming its own
        # sector, and that distinction matters, not just two numbers
        # sitting next to each other unremarked.
        if rs_drawdown is not None and rs_drawdown > -15 and sector_dd <= -20:
            print("    -> Outperforming the broader market but genuinely lagging comparable peers - worth noting")

    sector_strength = compute_sector_strength_context(ticker)
    if sector_strength:
        print()
        pct_rank = round((1 - (sector_strength["rank"] - 1) / sector_strength["total_sectors"]) * 100)
        print(f"  Sector Strength  : {sector_strength['sector']} ranks #{sector_strength['rank']} "
              f"of {sector_strength['total_sectors']} sectors (top {pct_rank}%), "
              f"RS {sector_strength['rs_score']:+.1f}%  [as of {sector_strength['run_date']}]")
        if sector_strength["rank"] <= max(3, sector_strength["total_sectors"] // 10):
            print("    -> A genuinely leading sector right now - real, current theme/sector momentum behind this stock")
        elif sector_strength["rank"] > sector_strength["total_sectors"] * 0.75:
            print("    -> A genuinely lagging sector right now - this stock is swimming against its own sector's current")

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

    if fundamentals:
        valuation = compute_valuation_comparison(ticker, fundamentals)
        if valuation:
            print()
            print(f"  === VALUATION PEER BASKET ({valuation['total_peers_available']} peers available) ===")
            pe_disp = f"{valuation['pe']}" if valuation['pe'] else "N/A"
            pe_sector_disp = f"{valuation['pe_sector_avg']}" if valuation['pe_sector_avg'] else "N/A"
            print(f"    P/E        : {pe_disp}  vs sector {pe_sector_disp}  ({valuation['pe_peer_count']} peers with valid P/E)")
            pb_disp = f"{valuation['pb']}" if valuation['pb'] else "N/A"
            pb_sector_disp = f"{valuation['pb_sector_avg']}" if valuation['pb_sector_avg'] else "N/A"
            print(f"    P/B        : {pb_disp}  vs sector {pb_sector_disp}  ({valuation['pb_peer_count']} peers with valid P/B)")
            ev_disp = f"{valuation['ev_ebitda']}" if valuation['ev_ebitda'] else "N/A"
            ev_sector_disp = f"{valuation['ev_ebitda_sector_avg']}" if valuation['ev_ebitda_sector_avg'] else "N/A"
            print(f"    EV/EBITDA  : {ev_disp}  vs sector {ev_sector_disp}  ({valuation['ev_ebitda_peer_count']} peers with valid EV/EBITDA)")

        growth = compute_growth_cagr(ticker)
        if growth:
            print()
            print("  === GROWTH (CAGR) ===")
            for label, name in [("revenue", "Revenue"), ("net_profit", "Net Profit"), ("eps", "EPS")]:
                cagr_3y = growth.get(f"{label}_cagr_3y")
                cagr_5y = growth.get(f"{label}_cagr_5y")
                cagr_3y_str = f"{cagr_3y:+.1f}%" if cagr_3y is not None else "N/A (insufficient history)"
                cagr_5y_str = f"{cagr_5y:+.1f}%" if cagr_5y is not None else "N/A (insufficient history)"
                print(f"    {name:<11}: 3Y {cagr_3y_str}  |  5Y {cagr_5y_str}")

        fcf_history = compute_free_cash_flow_history(ticker)
        if fcf_history:
            print()
            print("  === FREE CASH FLOW (last 5 years) ===")
            for date_str, val in fcf_history:
                # yfinance returns absolute rupees, not crores (confirmed
                # via the earlier totalDebt investigation showing a raw,
                # un-scaled figure) - converting explicitly rather than
                # mislabeling a raw absolute value as "Cr"
                val_cr = val / 1e7
                print(f"    {date_str}: Rs{val_cr:,.0f} Cr")

        de_trend = compute_debt_to_equity_trend(ticker)
        if de_trend:
            print()
            print("  === DEBT-TO-EQUITY (5-year trend) ===")
            for date_str, de_val in de_trend:
                print(f"    {date_str}: {de_val}")

        health = compute_financial_health_extended(ticker)
        if health and any(v is not None for v in health.values()):
            print()
            print("  === FINANCIAL HEALTH (additional) ===")
            if health["current_ratio"] is not None:
                print(f"    Current Ratio      : {health['current_ratio']}")
            if health["ebitda_margin"] is not None:
                print(f"    EBITDA Margin      : {health['ebitda_margin']}%")
            if health["interest_coverage"] is not None:
                print(f"    Interest Coverage  : {health['interest_coverage']}x  (approx, EBIT ≈ Pretax Income + Interest Expense)")
            if health["roce"] is not None:
                print(f"    ROCE               : {health['roce']}%  (approx)")

        event_risk = compute_event_risk(ticker)
        if event_risk and event_risk["earnings_date"]:
            print()
            print("  === EVENT RISK ===")
            days = event_risk["days_to_earnings"]
            print(f"    Next Earnings      : {event_risk['earnings_date']}  ({days} days away)")
            if days is not None and 0 <= days <= 10:
                print(f"    ⚠ EARNINGS WITHIN {days} DAYS - a breakout right now carries genuinely different, "
                      f"event-driven risk, not a purely technical one")
            if event_risk["ex_dividend_date"]:
                print(f"    Ex-Dividend Date   : {event_risk['ex_dividend_date']}")

        div_history = compute_dividend_history(ticker)
        if div_history:
            print()
            if div_history["has_dividends"]:
                print(f"  Dividend History (last 5 years, {len(div_history['recent'])} payouts):")
                for date_str, amount in div_history["recent"][-5:]:
                    print(f"    {date_str}: Rs{amount}")
            else:
                print("  Dividend History: No dividends in the last 5 years")

    print()
    print("  === VALUE OPPORTUNITY ===")
    fib_zone = compute_fibonacci_value_zone(ticker)
    if fib_zone:
        print(f"  Value Zone (Fibonacci 61.8%): {fib_zone['signal']} - zone {fib_zone['fib_zone']}, "
              f"stop {fib_zone['stop_loss']}, target {fib_zone['target']}")

    value_zone = None
    if fundamentals:
        print()
        print("  Value Zone (Fundamentals, 4 dimensions - fetches sector peers, adds real latency):")
        value_zone = compute_value_zone(ticker, fundamentals)
        if value_zone:
            for dimension, verdict in value_zone.items():
                if verdict:
                    print(f"    {dimension}: {verdict}")

    print(f"  Market Regime    : {regime}  (exposure {int(multiplier*100)}%)")

    # #66 - explicit, unmistakable summary distinguishing trading vs
    # value opportunity. Per real, direct feedback: a stock can score
    # highly on one and poorly on the other, and a momentum strategy
    # doesn't need value alignment - the UI should make this obvious,
    # not implied by section ordering alone.
    trading_label = "HIGH" if score >= 70 else ("MODERATE" if score >= 50 else "LOW")

    if value_zone:
        cheap_keywords = ["VALUE ZONE", "CHEAPER", "NEAR OWN 52-WEEK LOW", "undervalued"]
        expensive_keywords = ["NOT in value zone", "MORE EXPENSIVE", "NEAR OWN 52-WEEK HIGH", "overvalued"]
        cheap_count = sum(1 for v in value_zone.values() if v and any(k in v for k in cheap_keywords))
        expensive_count = sum(1 for v in value_zone.values() if v and any(k in v for k in expensive_keywords))
        value_label = "HIGH" if cheap_count > expensive_count else ("LOW" if expensive_count > cheap_count else "MIXED")
        value_detail = f"{cheap_count} of 4 dimensions cheap, {expensive_count} of 4 expensive"
    else:
        value_label = "UNKNOWN"
        value_detail = "fundamentals unavailable"

    print()
    print(f"  SUMMARY: {trading_label} Trading Opportunity (score {score}/100)  +  "
          f"{value_label} Value Opportunity ({value_detail})")
    if trading_label == "HIGH" and value_label == "LOW":
        print("    -> This is a momentum play, not a value play - that's not a contradiction, "
              "just know which one you're taking")

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

        exec_risk = compute_execution_risk(ticker, qty)
        if exec_risk:
            print("-" * 68)
            print("  Execution Risk (real, order-specific):")
            print(f"    Liquidity  : {exec_risk['pct_of_adv']}% of 20-day ADV ({exec_risk['adv_20d']:,} shares/day)")
            if exec_risk["pct_of_adv"] is not None and exec_risk["pct_of_adv"] > 10:
                print(f"      ⚠ Order is a genuinely large share of daily volume - expect real execution difficulty")
            if exec_risk["gap_risk_std_pct"] is not None:
                print(f"    Gap Risk   : {exec_risk['gap_risk_std_pct']}% (real historical overnight-gap std dev)")
            if exec_risk["slippage_estimate_pct"] is not None:
                print(f"    Slippage   : ~{exec_risk['slippage_estimate_pct']}% (rough estimate, NOT empirically "
                      f"calibrated - no real fill data exists to validate a coefficient against)")

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