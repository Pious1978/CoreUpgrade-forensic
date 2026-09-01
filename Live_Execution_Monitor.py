"""
Live_Execution_Monitor.py
-------------------------------------------------------------------------

Institutional Live Execution Terminal v2.0

Architecture:

Market Regime
      |
      |
Risk Positioning Engine
      |
      |
Trade Candidates
      |
      |
Live Price Engine
      |
      |
Execution State Machine
      |
      |
Execution Monitor

Features:
- Real-time surveillance
- State persistence
- Breakout lifecycle tracking
- Entry quality scoring
- Regime permissions
- Event logging
- Batch SQLite updates
- API latency telemetry

"""

import sqlite3
import pandas as pd
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


from core.config import DB_PATH, PARQUET_CACHE_DIR
from core.Live_Price_Engine import LivePriceEngine
from core.Execution_State_Machine import evaluate_trade
from core.notifications import send_alert
from core.technical_indicators import get_technical_context, compute_weekly_rvol, compute_atr
import math


INVALIDATED_STATES = ("STOP_BREACHED", "FAILED_BREAKOUT")

STATE_PRIORITY = {
    "VALID_BREAKOUT": 1,
    "RETEST_SUCCESS": 2,
    "LOW_VOLUME_BREAKOUT": 3,
    "TESTING": 4,
    "APPROACHING": 5,
    "BASE_BUILDING": 6,
    "EXTENDED": 7,
    "WAITING": 8,
}

PRIORITY_ALERT_STATES = ("VALID_BREAKOUT", "RETEST_SUCCESS")

# How many rows to print in the "RECENTLY INVALIDATED" list before
# collapsing the rest into a single summary line. Without a cap this
# list prints every STOP_BREACHED/FAILED_BREAKOUT candidate (which can
# be 500+ names in a choppy regime) on every 60-second cycle.
INVALIDATED_DISPLAY_LIMIT = 15

# Extension-based sizing rejection: a breakout that has already run too
# far past its pivot, or whose remaining reward-to-risk has eroded too
# much, isn't worth chasing even if it's technically a valid breakout.
# 2.0% was chosen by checking real candidates against several thresholds -
# it kept genuinely fresh breakouts (Ext ~1.2-1.6%) sized normally while
# filtering out the ones that had already run further (Ext >2.6%) or had
# poor remaining R - not a value copied from Alpha1's own threshold,
# which real testing showed would have rejected several good setups.
EXTENSION_REJECT_PCT = 2.0
MIN_REMAINING_R = 1.2

# Candle-body-ratio fakeout detection: distinguishes a genuine, sustained
# breakout (closed near the session high) from a wick-driven fakeout
# (spiked up on volume, then fell back and closed weak).
FAKEOUT_BODY_RATIO_THRESHOLD = 0.4



# ================================================================
# MARKET REGIME
# ================================================================

def get_market_state():

    try:

        conn = sqlite3.connect(DB_PATH)

        df = pd.read_sql("""
            SELECT 
                regime,
                composite_score,
                confidence,
                position_multiplier
            FROM market_regime
            ORDER BY date DESC
            LIMIT 1

        """, conn)

        conn.close()


        if df.empty:

            return {
                "regime":"NEUTRAL",
                "score":0,
                "confidence":"LOW",
                "multiplier":0.25
            }


        row=df.iloc[0]


        return {

            "regime":row["regime"],
            "score":float(row["composite_score"]),
            "confidence":row["confidence"],
            "multiplier":float(row["position_multiplier"])

        }


    except Exception:

        return {

            "regime":"NEUTRAL",
            "score":0,
            "confidence":"LOW",
            "multiplier":0.25
        }



def is_market_open():
    """
    Real NSE market hours check - 9:15 AM to 3:30 PM IST, weekdays only.
    Previously the monitor had zero awareness of this at all, and would
    keep refreshing indefinitely even hours after close, showing stale
    prices and meaningless intraday RVOL (confirmed directly - a real
    session kept running at 16:44, well past the 3:30 PM close).

    Does not account for NSE holidays (Diwali, Republic Day, etc.) -
    that would need an external holiday calendar, out of scope here.
    A weekday + time-window check covers the most common real case
    (nights and weekends) without needing that extra dependency.
    """

    now = datetime.now()

    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return market_open <= now <= market_close


# ================================================================
# EXECUTION HISTORY
# ================================================================


def init_execution_db():

    conn=sqlite3.connect(DB_PATH)

    cur=conn.cursor()


    cur.execute("""
    CREATE TABLE IF NOT EXISTS execution_events
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        previous_state TEXT,
        new_state TEXT,
        price REAL,
        rvol REAL,
        timestamp TEXT
    )
    """)


    # trade_candidates (written by Risk_Positioning_Engine.py) doesn't
    # have the live-tracking columns this monitor needs to persist state
    # into. Add them here, idempotently, so this is safe to run every day.
    new_columns = [
        ("execution_state", "TEXT"),
        ("last_price", "REAL"),
        ("distance_pct", "REAL"),
        ("live_rvol", "REAL"),
        ("last_signal_time", "TEXT"),
        ("t1_hit", "INTEGER"),
    ]

    for col_name, col_type in new_columns:
        try:
            cur.execute(f"ALTER TABLE trade_candidates ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                raise


    conn.commit()
    conn.close()



def log_event(
        ticker,
        old_state,
        new_state,
        price,
        rvol):


    conn=sqlite3.connect(DB_PATH)

    cur=conn.cursor()


    cur.execute("""
    INSERT INTO execution_events
    (
    ticker,
    previous_state,
    new_state,
    price,
    rvol,
    timestamp
    )
    VALUES (?,?,?,?,?,?)

    """,
    (
        ticker,
        old_state,
        new_state,
        price,
        rvol,
        datetime.now().isoformat()
    ))


    conn.commit()
    conn.close()



# ================================================================
# PRICE FETCHING
# ================================================================


def fetch_quote(ticker):

    start=time.time()

    quote=LivePriceEngine.get_live_quote(ticker)

    quote["latency"]=round(
        time.time()-start,
        2
    )

    return ticker,quote



# ================================================================
# OPEN POSITIONS (real, actually-held - from Trade_Journal.py)
# ================================================================


def fetch_open_positions(conn):
    """
    Reads real, actually-held positions from trade_journal (status=
    'EXECUTED') - these are trades you've told Trade_Journal.py you
    genuinely took, with your real entry price and quantity, not the
    hypothetical pivot-based numbers everything else in this board uses.

    entry_shares is reduced by anything already logged as a partial exit
    in trade_journal_exits, so this reflects what you're actually still
    holding right now, not the original full entry size.
    """

    try:
        df = pd.read_sql("""
            SELECT id, ticker, entry_price, entry_date, entry_shares,
                   planned_stop, planned_target_1, planned_target_2, pattern
            FROM trade_journal
            WHERE status='EXECUTED'
        """, conn)

        if df.empty:
            return df

        try:
            exits_df = pd.read_sql("""
                SELECT journal_id, SUM(exit_shares) as exited
                FROM trade_journal_exits
                GROUP BY journal_id
            """, conn)

            exits_map = dict(zip(exits_df["journal_id"], exits_df["exited"])) if not exits_df.empty else {}

        except Exception:
            exits_map = {}

        df["entry_shares"] = df.apply(
            lambda row: row["entry_shares"] - exits_map.get(row["id"], 0),
            axis=1
        )

        # A position fully exited via partial trails (remaining=0) but
        # not yet marked CLOSED (edge case, shouldn't normally happen
        # since log_exit() closes it automatically) shouldn't display
        # as an open position with zero or negative shares.
        return df[df["entry_shares"] > 0]

    except Exception:
        return pd.DataFrame()


def evaluate_position(entry_price, current_price, planned_stop, planned_target_1, planned_target_2, entry_shares):
    """
    Real post-entry management using your actual entry price as the
    baseline - not the hypothetical pivot. This is the one place in the
    whole system that reflects what you're genuinely holding, not what
    the scanners are still considering.
    """

    unrealized_pnl = round((current_price - entry_price) * entry_shares, 2)
    unrealized_pct = round(((current_price - entry_price) / entry_price) * 100, 2) if entry_price > 0 else 0.0

    if planned_stop and current_price <= planned_stop:
        action = f"STOP ALERT - price at or below your planned stop Rs{planned_stop:.2f}, consider exiting"

    elif planned_target_1 and current_price >= planned_target_1:
        action = f"T1 REACHED - trail stop to breakeven Rs{entry_price:.2f}, consider taking partial profit"

    elif planned_stop and current_price > planned_stop:
        dist_to_stop = round(((current_price - planned_stop) / current_price) * 100, 1)
        action = f"HOLDING - {dist_to_stop}% above your stop, monitor"

    else:
        action = "HOLDING - no stop on file, monitor manually"

    return unrealized_pnl, unrealized_pct, action



# ================================================================
# DATABASE UPDATE
# ================================================================


def update_states(updates):


    conn=sqlite3.connect(DB_PATH)

    cur=conn.cursor()


    cur.executemany("""

    UPDATE trade_candidates

    SET

    execution_state=?,
    last_price=?,
    distance_pct=?,
    live_rvol=?,
    last_signal_time=?,
    t1_hit=?

    WHERE ticker=?

    """,
    updates)


    conn.commit()
    conn.close()



# ================================================================
# ENTRY SCORE
# ================================================================


def calculate_conviction_score(
        rs_percentile,
        delivery_score,
        accumulation_ratio,
        base_compression,
        cup_handle_quality,
        hybrid_alpha_score,
        intraday_rvol,
        weekly_rvol,
        pivot_extension,
        remaining_r,
        distance
):
    """
    Returns (conviction, opportunity, readiness) - three related numbers
    from one underlying calculation, not three separate ones, so they
    stay mathematically consistent by construction (0.70*opportunity +
    0.30*readiness always exactly equals conviction).

    conviction: the original, single blended score (kept for board
    sorting and get_hold_period, unchanged from before).

    opportunity: "is this fundamentally a good setup" - relative_strength
    + institutional + structure (70% of total weight, renormalized to
    100%). Independent of live timing.

    readiness: "is this ready to act on right now" - confirmation/tape +
    risk (30% of total weight, renormalized to 100%). Purely live,
    timing-driven factors.

    This mirrors Alpha1's Opportunity/Readiness split conceptually, but
    unlike Alpha1 (which used the same underlying number at two
    different thresholds), these are two genuinely independent
    sub-calculations, not the same score read two different ways.

    Built from real, individually-verified factors (checked against
    known-active real breakout stocks before use - rs_percentile,
    delivery_score, and accumulation_ratio all confirmed genuinely
    differentiated; hybrid_alpha confirmed to be a legitimate narrow
    "classic VCP shape" signal, not broken data, despite several real
    stocks correctly tying at the same low value for genuinely not
    matching that specific pattern).

    Weighted using this system's own core/factor_registry.py family
    weights (relative_strength 30%, institutional 20%, structure 20%,
    confirmation 15%, risk_liquidity 15%), not arbitrary values -
    rs_acceleration (a small sub-component of relative_strength) is
    excluded since it's genuinely unpopulated across the board;
    cup_handle_quality is only used when present (most stocks legitimately
    don't have a cup-and-handle pattern at all).
    """

    # Relative Strength (30%)
    relative_strength = rs_percentile if rs_percentile is not None else 50.0

    # Institutional (20%)
    institutional = (
        (delivery_score if delivery_score is not None else 50.0) * 0.6 +
        (accumulation_ratio * 100 if accumulation_ratio is not None else 50.0) * 0.4
    )

    # Structure (20%) - only blends components that are actually present
    structure_components = [
        (base_compression * 100 if base_compression is not None else None, 0.6),
        (hybrid_alpha_score * 100 if hybrid_alpha_score is not None else None, 0.2),
        (cup_handle_quality * 100 if cup_handle_quality is not None else None, 0.2),
    ]
    available = [(v, w) for v, w in structure_components if v is not None]
    total_w = sum(w for v, w in available)
    structure = sum(v * w for v, w in available) / total_w if total_w > 0 else 50.0

    # Confirmation/Tape (15%) - live data, reusing the same rvol*40
    # mapping convention already established for the old blended score
    tape_components = []
    if intraday_rvol is not None:
        tape_components.append((min(100, intraday_rvol * 40), 0.4))
    if weekly_rvol is not None:
        tape_components.append((min(100, weekly_rvol * 40), 0.3))
    if pivot_extension is not None:
        tape_components.append((pivot_extension * 100, 0.3))
    total_w2 = sum(w for v, w in tape_components)
    tape = sum(v * w for v, w in tape_components) / total_w2 if total_w2 > 0 else 50.0

    # Risk (15%) - live data
    risk = (
        min(100, (remaining_r * 35 if remaining_r is not None else 50)) * 0.6 +
        max(0, 100 - abs(distance) * 20) * 0.4
    )

    conviction = round(
        relative_strength * 0.30 +
        institutional * 0.20 +
        structure * 0.20 +
        tape * 0.15 +
        risk * 0.15,
        1
    )

    opportunity = round(
        relative_strength * (0.30/0.70) +
        institutional * (0.20/0.70) +
        structure * (0.20/0.70),
        1
    )

    readiness = round(
        tape * 0.5 +
        risk * 0.5,
        1
    )

    return conviction, opportunity, readiness


def calculate_edp(distance_pct, atr_pct):
    """
    Expected Days to Pivot - how many trading days, at the stock's own
    ATR-implied daily movement, it might take to close the gap to pivot.
    Only meaningful for stocks that haven't triggered yet (APPROACHING,
    BASE_BUILDING, TESTING) - a stock already at/past its pivot has
    already closed this gap.

    Formula verified against real output - exact match on real stocks
    (FEDERALBNK: 3.82 expected days -> "4-6 Days", ANANDRATHI: 1.204
    expected days -> "2 Trading Days"), and re-verified directly against
    real APPROACHING and BASE_BUILDING stocks in this system's own
    database (APPROACHING stocks structurally cluster at "1 Trading Day"
    given the state's tight 0-3% definition combined with typical real
    ATR of 2-3% - genuine differentiation shows up in BASE_BUILDING,
    which has no upper bound on distance).
    """

    if atr_pct is None or atr_pct <= 0:
        return None

    expected_days = abs(distance_pct) / (atr_pct + 1e-8)

    if expected_days <= 1.2:
        return "1 Trading Day"
    elif expected_days <= 3.0:
        return f"{math.ceil(expected_days)} Trading Days"
    else:
        return f"{math.ceil(expected_days)}-{math.ceil(expected_days*1.5)} Days"


def fetch_time_in_state(conn):
    """
    Bulk-fetches, for every (ticker, state) pair ever logged, the most
    recent timestamp that ticker entered that state - using
    execution_events, which is append-only and survives the nightly
    trade_candidates rebuild (unlike execution_state/last_signal_time on
    trade_candidates itself, which get wiped fresh every night). This
    also means time-in-state genuinely persists across separate
    monitoring sessions, not just within a single day's run.
    """

    try:
        df = pd.read_sql("""
            SELECT ticker, new_state, MAX(timestamp) as entered_at
            FROM execution_events
            GROUP BY ticker, new_state
        """, conn)

        lookup = {}

        for _, row in df.iterrows():
            key = (str(row["ticker"]).upper().strip(), row["new_state"])
            lookup[key] = row["entered_at"]

        return lookup

    except Exception:
        return {}


def format_time_in_state(entered_at_str):

    if not entered_at_str:
        return None

    try:
        entered_at = datetime.fromisoformat(entered_at_str)
    except (ValueError, TypeError):
        return None

    elapsed = datetime.now() - entered_at
    total_minutes = int(elapsed.total_seconds() / 60)

    if total_minutes < 0:
        return None

    if total_minutes < 60:
        return f"{total_minutes}m"

    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours < 24:
        return f"{hours}h {minutes}m"

    days = hours // 24

    return f"{days}d {hours % 24}h"


def fetch_factor_lookup(conn):
    """
    Bulk-fetches the real factor data the conviction score needs, once
    per cycle - not one query per stock, which would be far too slow
    across hundreds of candidates. Returns a dict keyed by clean ticker.
    """

    lookup = {}

    try:
        snapshot_df = pd.read_sql("""
            SELECT symbol, rs_percentile, delivery_score
            FROM daily_snapshot
            WHERE date = (SELECT MAX(date) FROM daily_snapshot)
        """, conn)

        for _, row in snapshot_df.iterrows():
            ticker = str(row["symbol"]).upper().strip()
            lookup.setdefault(ticker, {})["rs_percentile"] = row["rs_percentile"]
            lookup[ticker]["delivery_score"] = row["delivery_score"]

    except Exception:
        pass

    try:
        factor_names = ("accumulation_ratio", "base_compression", "cup_handle_quality", "hybrid_alpha_score", "pivot_extension")

        factors_df = pd.read_sql(f"""
            SELECT ticker, factor_name, score
            FROM scanner_factors
            WHERE factor_name IN {factor_names}
            AND date = (SELECT MAX(date) FROM scanner_factors)
        """, conn)

        for _, row in factors_df.iterrows():
            ticker = str(row["ticker"]).upper().strip()
            lookup.setdefault(ticker, {})[row["factor_name"]] = row["score"]

    except Exception:
        pass

    return lookup


def get_read(state, discount_pct, vdry_ratio, rvol, body_ratio=None):
    """
    Translates the raw board metrics into a short, plain-language verdict -
    synthesis of what the existing numbers already say, not a new signal.
    """

    if state == "STOP_BREACHED":

        if rvol is not None and rvol >= 2.0:
            return f"STOP HIT ON HEAVY VOLUME - RVOL {rvol}x, likely genuine breakdown, do not expect a bounce"

        elif rvol is not None and rvol < 0.7:
            return f"STOP HIT ON LIGHT VOLUME - RVOL {rvol}x, could be a shakeout, but still respect the stop"

        else:
            return "STOP HIT - setup invalidated, below calculated stop"

    if state == "FAILED_BREAKOUT":
        return "BREAKOUT FAILED - fell back below pivot after triggering"

    # Fakeout check takes priority over a plain "confirmed breakout" read -
    # a weak candle body on a breakout day is a real warning sign a volume
    # spike alone doesn't capture (RVOL can be high on a fakeout too).
    if state in ("VALID_BREAKOUT", "LOW_VOLUME_BREAKOUT") and body_ratio is not None and body_ratio < FAKEOUT_BODY_RATIO_THRESHOLD:
        return f"POSSIBLE FAKEOUT - spiked but closed weak (body ratio {body_ratio}), verify before acting"

    if rvol is not None and rvol >= 3.0:
        return f"VOLUME SPIKE - RVOL {rvol}x normal, verify catalyst before acting"

    if state == "VALID_BREAKOUT":
        return "CONFIRMED BREAKOUT - crossed pivot with volume confirmation"

    if state == "LOW_VOLUME_BREAKOUT":
        return "BREAKOUT UNCONFIRMED - crossed pivot but volume below 1.5x threshold"

    if state == "RETEST_SUCCESS":
        return "RETEST HOLDING - pulled back to pivot and held"

    if discount_pct is not None and vdry_ratio is not None:

        if discount_pct > 8 and vdry_ratio > 1.2:
            return f"EXTENDED - up {discount_pct}% from EMA20, volume expanding, not a fresh coil"

        if abs(discount_pct) < 2 and vdry_ratio < 0.7:
            return "TIGHT - resting at EMA20, volume contracting, classic pre-breakout coil"

        if vdry_ratio < 0.5:
            return f"QUIET - volume drying up ({vdry_ratio}x baseline), watch for a trigger"

    fallback = {
        "BASE_BUILDING": "FORMING - still well below pivot",
        "APPROACHING": "APPROACHING - nearing pivot, not yet triggered",
        "TESTING": "AT PIVOT - testing the breakout level now",
        "WAITING": "NO SIGNAL YET",
        "EXTENDED": "EXTENDED - already well above trigger",
    }

    return fallback.get(state, state)


def get_hold_period(score):
    """
    Suggested review point within a 1-2 week swing-trade hold, scaled by
    the blended entry score (calculate_entry_score output), calibrated to
    its real observed range (~20-70) rather than an assumed 0-100 range.

    This originally used composite_score, but that value turned out to be
    exactly 1.0 for nearly every candidate in trade_candidates - a real,
    separate issue in Master_Terminal.py where Composite_Score is built
    from rank(pct=True) (percentile rank) over a currently small candidate
    pool (most of the universe still fails each scanner's minimum-history
    gate at ~38-40 real trading days). With a small pool, the top-ranked
    stock lands near the 100th percentile almost by construction,
    regardless of its true absolute quality - this should self-correct as
    more bhav-copy history accumulates and candidate pools grow. Using
    composite_score here provided zero differentiation in the meantime, so
    this uses the blended score instead, which is not subject to the same
    small-pool collapse.
    """

    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 20.0

    clamped = max(20, min(70, s))
    hold_days = round(5 + ((clamped - 20) / 50) * 5)

    if hold_days <= 5:
        conviction = "lower conviction setup"
    elif hold_days <= 7:
        conviction = "moderate conviction setup"
    else:
        conviction = "higher conviction setup"

    return f"Review at {hold_days} trading days - {conviction}"



# ================================================================
# MAIN ENGINE
# ================================================================


def run_live_monitor(total_capital):


    init_execution_db()


    previous_states={}


    cycle=0



    while True:


        cycle+=1

        start=time.time()

        timestamp=datetime.now().strftime("%H:%M:%S")

        if not is_market_open():
            print()
            print("="*75)
            print(f"MARKET CLOSED as of {timestamp} - stopping live monitoring.")
            print("Prices and RVOL become stale/meaningless once trading ends for the day;")
            print("re-run this tool tomorrow during market hours (9:15 AM - 3:30 PM IST).")
            print("="*75)
            break

        market=get_market_state()


        regime=market["regime"]

        multiplier=market["multiplier"]



        if multiplier>=0.75:

            mode="FULL_EXECUTION"

        elif multiplier>=0.5:

            mode="SELECTIVE_EXECUTION"

        else:

            mode="WATCH_ONLY"



        conn=sqlite3.connect(DB_PATH)


        df=pd.read_sql("""

        SELECT *
        FROM trade_candidates
        ORDER BY composite_score DESC

        """,conn)


        factor_lookup = fetch_factor_lookup(conn)

        open_positions_df = fetch_open_positions(conn)

        time_in_state_lookup = fetch_time_in_state(conn)


        conn.close()



        if df.empty:

            print("No candidates available")

            time.sleep(60)

            continue



        quotes={}


        with ThreadPoolExecutor(max_workers=10) as executor:


            futures=[

                executor.submit(
                    fetch_quote,
                    x
                )

                for x in df["ticker"]

            ]


            for f in as_completed(futures):

                ticker,quote=f.result()

                quotes[ticker]=quote


        # Open positions may include tickers no longer in today's scan
        # (entered on a past day, since dropped out of trade_candidates) -
        # fetch quotes for those separately rather than assume overlap.
        position_results = []

        if not open_positions_df.empty:

            position_tickers = [t for t in open_positions_df["ticker"] if t not in quotes]

            if position_tickers:

                with ThreadPoolExecutor(max_workers=10) as executor:

                    futures = [executor.submit(fetch_quote, t) for t in position_tickers]

                    for f in as_completed(futures):
                        ticker, quote = f.result()
                        quotes[ticker] = quote

            for _, prow in open_positions_df.iterrows():

                ticker = prow["ticker"]
                quote = quotes.get(ticker, {})
                current_price = quote.get("ltp", 0)

                if current_price <= 0:
                    continue

                unrealized_pnl, unrealized_pct, action = evaluate_position(
                    entry_price=float(prow["entry_price"]),
                    current_price=current_price,
                    planned_stop=float(prow["planned_stop"]) if prow["planned_stop"] else 0,
                    planned_target_1=float(prow["planned_target_1"]) if prow["planned_target_1"] else 0,
                    planned_target_2=float(prow["planned_target_2"]) if prow["planned_target_2"] else 0,
                    entry_shares=int(prow["entry_shares"])
                )

                position_results.append({
                    "ticker": ticker,
                    "entry_price": float(prow["entry_price"]),
                    "entry_date": prow["entry_date"],
                    "entry_shares": int(prow["entry_shares"]),
                    "current_price": current_price,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pct": unrealized_pct,
                    "action": action,
                })


        updates=[]

        board=[]


        counters={}


        for _,row in df.iterrows():


            ticker=row["ticker"]

            pivot=float(row["pivot"])

            trigger=float(
                row.get(
                    "breakout_trigger",
                    pivot*1.005
                )
            )


            old_state=row.get(
                "execution_state",
                "WAITING"
            )

            t1_hit_raw = row.get("t1_hit", 0)
            t1_hit_prev = int(t1_hit_raw) if pd.notna(t1_hit_raw) else 0
            target_1_check = float(row.get("target_1", 0))



            quote=quotes.get(
                ticker,
                {}
            )


            price=quote.get(
                "ltp",
                row.get("last_price",pivot)
            )


            rvol=quote.get(
                "rvol",
                1.0
            )


            distance=round(

                ((price-pivot)/pivot)*100,

                2

            )


            stop_loss_check = float(row.get("stop_loss", 0))


            new_state=evaluate_trade(

                price,
                pivot,
                trigger,
                rvol,
                old_state,
                stop_loss=stop_loss_check

            )


            # T1-hit tracking: sticky once True (once price has reached
            # Target 1 since this stock first showed a confirmed breakout,
            # that fact doesn't reverse just because price pulls back
            # later). Note this is a forward-looking "would T1 have been
            # reached" signal, not confirmation of an actual held position -
            # this system doesn't yet track real entries (see Position
            # Monitor, still an open item).
            t1_hit_now = bool(t1_hit_prev) or (target_1_check > 0 and price >= target_1_check)


            counters[new_state]=counters.get(
                new_state,
                0
            )+1



            updates.append(

                (
                new_state,
                price,
                distance,
                rvol,
                datetime.now().strftime("%H:%M:%S"),
                int(t1_hit_now),
                ticker
                )

            )



            if new_state!=old_state:

                log_event(

                    ticker,
                    old_state,
                    new_state,
                    price,
                    rvol

                )

                if new_state == "VALID_BREAKOUT":
                    send_alert("VALID_BREAKOUT", ticker, "INFO",
                               f"Confirmed breakout at Rs{price:.2f}, RVOL {rvol}x")

                if new_state == "STOP_BREACHED":
                    send_alert("STOP_BREACHED", ticker, "CRITICAL",
                               f"Stop breached at Rs{price:.2f}")



            stop_loss = float(row.get("stop_loss", 0))
            target_1 = float(row.get("target_1", 0))
            target_2 = float(row.get("target_2", 0))
            shares_raw = row.get("shares", 0)
            planned_shares = int(shares_raw) if pd.notna(shares_raw) else 0
            tier = row.get("tier", "N/A")

            clean_ticker = str(ticker).replace(".NS","").upper().strip()
            tech = get_technical_context(clean_ticker)
            weekly_rvol = compute_weekly_rvol(clean_ticker)

            _, atr_pct = compute_atr(clean_ticker)

            edp = calculate_edp(distance, atr_pct)

            # Remaining R and target-distance percentages only make sense
            # while price is still above the stop - if the stop has been
            # breached, there is no "remaining" risk-reward left to show.
            if price - stop_loss > 0:
                remaining_r = round((target_1 - price) / (price - stop_loss), 2)
                t1_pct_away = round(((target_1 - price) / price) * 100, 1)
                t2_pct_away = round(((target_2 - price) / price) * 100, 1)
            else:
                remaining_r = None
                t1_pct_away = None
                t2_pct_away = None

            # Conviction score - replaces the earlier, simpler blended
            # score entirely. Built from real, individually-verified
            # factors via the bulk factor_lookup fetched once per cycle.
            factors = factor_lookup.get(clean_ticker, {})

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

            hold_period = get_hold_period(score)

            time_in_state_raw = time_in_state_lookup.get((clean_ticker, new_state))
            time_in_state = format_time_in_state(time_in_state_raw)

            # Candle-body-ratio - uses today's high/low from the same
            # intraday quote already fetched for RVOL, no extra API call.
            today_high = quote.get("high", 0)
            today_low = quote.get("low", 0)
            today_open_live = quote.get("open", 0)

            if today_high and today_low and today_high > today_low:
                body_ratio = round(abs(price - today_open_live) / (today_high - today_low), 2)
            else:
                body_ratio = None

            # Extension-based sizing rejection - a breakout that has
            # already run too far past pivot, or whose remaining R has
            # eroded too much, isn't worth sizing into even though it's
            # technically still a valid breakout state. Rejects sizing
            # only - the stock still shows on the board with its real
            # state, just without a trade plan. Must be determined before
            # total_shares/capital/loss are computed, so a rejection
            # correctly zeroes out everything downstream, not just the
            # share count.
            is_extended = distance > EXTENSION_REJECT_PCT
            is_poor_remaining_r = remaining_r is not None and remaining_r < MIN_REMAINING_R
            # Extension rejection only makes sense for a fresh entry
            # decision - once T1 has already been reached, the question
            # is "how many are left to manage," not "should I chase this
            # now," so a T1-hit stock is never rejected for being
            # extended (it's supposed to be extended by then).
            sizing_rejected = (not t1_hit_now) and new_state in PRIORITY_ALERT_STATES and (is_extended or is_poor_remaining_r)

            total_shares = 0 if sizing_rejected else planned_shares

            # Scale-out plan: split evenly between Target 1 and Target 2.
            # This is a suggested default, not a discovered rule - adjust
            # the split ratio here if you want a different plan (e.g. sell
            # more at T1 and let a smaller remainder ride to T2).
            sell_at_t1 = total_shares // 2
            sell_at_t2 = total_shares - sell_at_t1

            # Capital-aware fields - need real total_capital, entered
            # interactively when this script starts (same pattern as
            # Risk_Positioning_Engine.py).
            capital_used = round(total_shares * price, 2)
            capital_pct = round((capital_used / total_capital) * 100, 1) if total_capital > 0 else None

            # Max Loss uses pivot, not live price - this is the risk that
            # was actually budgeted when Risk_Positioning_Engine.py sized
            # this position (risk = pivot - stop). Using live price instead
            # would make this go negative and nonsensical once price has
            # already moved past the stop.
            #
            # If T1 has been reached, the 3-step plan calls for moving the
            # stop to breakeven (pivot) - reflect that in Max Loss too,
            # since the real downside risk from here on is now near zero,
            # not the original pre-breakout risk distance.
            effective_stop = pivot if t1_hit_now else stop_loss

            max_loss = round(total_shares * (pivot - effective_stop), 2)
            max_loss_pct = round((max_loss / total_capital) * 100, 2) if total_capital > 0 else None

            # sector_warning comes straight from a SQL/pandas column - if
            # a ticker has no warning on file, pandas represents that as
            # float('nan'), not None. bool(float('nan')) is True in
            # Python, so downstream "if x.get('sector_warning')" checks
            # were firing for every row and printing the literal string
            # "nan". pd.notna() normalizes the missing case to a real
            # None here, once, so nothing downstream has to special-case
            # NaN again.
            sector_warning_raw = row.get("sector_warning")
            sector_warning = sector_warning_raw if pd.notna(sector_warning_raw) else None

            board.append({

                "ticker":ticker,

                "score":score,

                "price":price,

                "qty":total_shares,

                "pivot":pivot,

                "stop_loss":stop_loss,

                "target_1":target_1,

                "target_2":target_2,

                "sell_at_t1":sell_at_t1,

                "sell_at_t2":sell_at_t2,

                "discount_pct":tech["discount_pct"],

                "vdry_ratio":tech["vdry_ratio"],

                "breach_pct": round(((stop_loss - price) / stop_loss) * 100, 2) if stop_loss > 0 and price < stop_loss else None,

                "distance":distance,

                "rvol":rvol,

                "weekly_rvol":weekly_rvol,

                "state":new_state,

                "tier":tier,

                "hold_period":hold_period,

                "capital_used":capital_used,

                "capital_pct":capital_pct,

                "max_loss":max_loss,

                "max_loss_pct":max_loss_pct,

                "remaining_r":remaining_r,

                "t1_pct_away":t1_pct_away,

                "t2_pct_away":t2_pct_away,

                "sizing_rejected":sizing_rejected,

                "sector_warning":sector_warning,

                "body_ratio":body_ratio,

                "t1_hit":t1_hit_now,

                "time_in_state":time_in_state,

                "opportunity":opportunity,

                "edp":edp,

                "readiness":readiness

            })



        update_states(updates)



        # Invalidated setups (stop already breached, or a breakout that
        # failed after triggering) don't belong in a ranked "top
        # candidates" board - showing a full Entry/Exit-Strategy block for
        # a dead setup is misleading, not just noisy. They get a short,
        # separate, unranked list instead.
        active_board = [x for x in board if x["state"] not in INVALIDATED_STATES]

        invalidated_board = [x for x in board if x["state"] in INVALIDATED_STATES]

        # Sort the top board purely by conviction score. This used to
        # sort by (STATE_PRIORITY, -score), which meant every state tier
        # was fully sorted internally but the tiers were then just
        # stacked one after another - e.g. every LOW_VOLUME_BREAKOUT
        # candidate (any score) outranked every TESTING candidate (any
        # score), so the board wasn't actually one ranked list, it was
        # several disconnected ones stitched together. Sorting on score
        # alone gives a genuine "best 10 candidates" board regardless of
        # which state they're currently in.
        active_board=sorted(

            active_board,

            key=lambda x: -x["score"]

        )

        priority_alerts = [x for x in active_board if x["state"] in PRIORITY_ALERT_STATES]



        duration=round(
            time.time()-start,
            2
        )


        # Real correction to the earlier screen-clear fix: it went too
        # far, wiping out the previous cycle's results entirely with no
        # way to scroll back and see them. A clear visual separator
        # achieves the original goal (distinguishing one cycle from the
        # next) without destroying history - especially since the
        # content itself is now far more compact than before (full
        # detail only for the genuinely few priority alerts, not all 10
        # candidates), so the original "endless wall of text" concern
        # is already substantially addressed by that alone.
        print("\n\n" + "#" * 75)
        print(f"# NEW CYCLE - {datetime.now().strftime('%H:%M:%S')}")
        print("#" * 75)

        print("\n"+"="*75)

        print(
            f"LIVE EXECUTION TERMINAL | {timestamp}"
        )

        print("="*75)


        print(
            f"Regime       : {regime}"
        )

        print(
            f"Exposure     : {int(multiplier*100)}%"
        )

        print(
            f"Mode         : {mode}"
        )

        print(
            f"Candidates   : {len(df)}"
        )

        print(
            f"Capital      : Rs{total_capital:,.0f}"
        )


        if position_results:

            total_unrealized = round(sum(p["unrealized_pnl"] for p in position_results), 2)

            print()

            print(f"  OPEN POSITIONS - what you actually hold ({len(position_results)}, unrealized P&L: Rs{total_unrealized:,.0f})")

            print("  " + "-"*66)

            for p in position_results:

                print(
                    f"  {p['ticker']:<12} Entry Rs{p['entry_price']:<9.2f} "
                    f"Now Rs{p['current_price']:<9.2f} "
                    f"Rs{p['unrealized_pnl']:<8,.0f} ({p['unrealized_pct']:+.1f}%)"
                )

                print(f"    -> {p['action']}")


        if priority_alerts:

            print()

            print(f"  PRIORITY ALERTS - look here first ({len(priority_alerts)})")

            print("  " + "-"*66)

            for x in priority_alerts:

                print(

                f"  {x['ticker']:<12} {x['state']:<16} "
                f"Rs{x['price']:<9.2f} Entry near pivot Rs{x['pivot']:<9.2f} "
                f"Score {x['score']}"

                )


        print("\nSTATE DISTRIBUTION")


        for k,v in counters.items():

            print(
                f"{k:<22}: {v}"
            )


        print("\nTOP PICK - FULL DETAIL")

        # Real, direct reuse of Stock_Lookup.py's own, already-tested
        # rich display - "same logic, one caller," not a duplicated
        # format. Local import (not at module level) is deliberate:
        # Stock_Lookup.py imports FROM this file at module level
        # already, so a top-level import here would create a genuine
        # circular import - confirmed and tested before applying this.
        top_pick = priority_alerts[0] if priority_alerts else (active_board[0] if active_board else None)

        if top_pick:
            from Stock_Lookup import lookup
            lookup(top_pick["ticker"], total_capital)

            other_alerts = [a for a in priority_alerts if a["ticker"] != top_pick["ticker"]]
            if other_alerts:
                print(f"\n  Also flagged ({len(other_alerts)} more, run Stock_Lookup.py individually): "
                      + ", ".join(a["ticker"] for a in other_alerts[:5]))
        else:
            print("  No candidates to show.")


        if invalidated_board:

            total_count = len(active_board) + len(invalidated_board)

            invalidation_rate = round((len(invalidated_board) / total_count) * 100, 1)

            print("\n" + "-"*68)

            print(
                f"  RECENTLY INVALIDATED  |  Rate: {invalidation_rate}% ({len(invalidated_board)}/{total_count})"
            )

            if invalidation_rate >= 60:

                print(
                    "  -> Unusually high - worth treating today's setups with added caution"
                )

            elif invalidation_rate >= 30:

                print(
                    "  -> Elevated"
                )

            print("-"*68)

            sorted_invalidated = sorted(
                invalidated_board,
                key=lambda x: x.get("breach_pct") or 0,
                reverse=True
            )

            # Print only the worst INVALIDATED_DISPLAY_LIMIT breaches in
            # full, then collapse everything past that into one summary
            # line. Previously this printed every invalidated candidate
            # (546 in a choppy regime) on every 60-second cycle.
            for x in sorted_invalidated[:INVALIDATED_DISPLAY_LIMIT]:

                breach_str = f"{x['breach_pct']}% below stop" if x.get("breach_pct") is not None else "N/A"

                rvol = x.get("rvol")

                if x['state'] == "STOP_BREACHED" and rvol is not None and rvol >= 2.0:
                    volume_note = f" [HEAVY VOL {rvol}x]"
                elif x['state'] == "STOP_BREACHED" and rvol is not None and rvol < 0.7:
                    volume_note = f" [light vol {rvol}x, possible shakeout]"
                else:
                    volume_note = ""

                print(
                    f"  {x['ticker']:<12} {x['state']:<16} {breach_str}{volume_note}"
                )

            remaining = len(sorted_invalidated) - INVALIDATED_DISPLAY_LIMIT

            if remaining > 0:

                tail = sorted_invalidated[INVALIDATED_DISPLAY_LIMIT:]

                avg_breach = round(
                    sum((x.get("breach_pct") or 0) for x in tail) / remaining,
                    1
                )

                print(
                    f"  ... +{remaining} more invalidated (avg {avg_breach}% below stop)"
                )



        print("\n" + "-"*75)

        print(
            f"Cycle Time : {duration}s"
        )

        print(
            "Next Scan : 60 seconds"
        )

        print("="*75)



        time.sleep(60)



if __name__=="__main__":

    while True:

        capital_input = input(
            "Enter your total trading capital (Rs): "
        ).strip()

        try:

            capital_value = float(capital_input)

            if capital_value <= 0:
                print("Capital must be a positive number. Please try again.")
                continue

            break

        except ValueError:
            print("Please enter a valid number (e.g. 500000).")


    run_live_monitor(total_capital=capital_value)