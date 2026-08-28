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
from core.technical_indicators import get_technical_context


INVALIDATED_STATES = ("STOP_BREACHED", "FAILED_BREAKOUT")



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
    last_signal_time=?

    WHERE ticker=?

    """,
    updates)


    conn.commit()
    conn.close()



# ================================================================
# ENTRY SCORE
# ================================================================


def calculate_entry_score(
        execution_score,
        regime,
        distance,
        rvol):


    regime_score={

        "CONFIRMED_UPTREND":100,

        "EARLY_RECOVERY":75,

        "CHOPPY_ACCUMULATION":60,

        "DISTRIBUTION":30,

        "BEAR":20

    }.get(
        regime,
        40
    )


    rvol_score=min(
        100,
        rvol*40
    )


    proximity=max(
        0,
        100-abs(distance)*20
    )


    return round(

        execution_score*0.4
        +
        regime_score*0.25
        +
        rvol_score*0.20
        +
        proximity*0.15,

        1
    )


def get_read(state, discount_pct, vdry_ratio, rvol):
    """
    Translates the raw board metrics into a short, plain-language verdict -
    synthesis of what the existing numbers already say, not a new signal.
    """

    if state == "STOP_BREACHED":
        return "STOP HIT - setup invalidated, below calculated stop"

    if state == "FAILED_BREAKOUT":
        return "BREAKOUT FAILED - fell back below pivot after triggering"

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



            score=calculate_entry_score(

                float(row.get(
                    "execution_score",
                    50
                )),

                regime,

                distance,

                rvol

            )


            stop_loss = float(row.get("stop_loss", 0))
            target_1 = float(row.get("target_1", 0))
            target_2 = float(row.get("target_2", 0))
            total_shares = int(row.get("shares", 0))
            tier = row.get("tier", "N/A")
            hold_period = get_hold_period(score)

            # Scale-out plan: split evenly between Target 1 and Target 2.
            # This is a suggested default, not a discovered rule - adjust
            # the split ratio here if you want a different plan (e.g. sell
            # more at T1 and let a smaller remainder ride to T2).
            sell_at_t1 = total_shares // 2
            sell_at_t2 = total_shares - sell_at_t1
            clean_ticker = str(ticker).replace(".NS","").upper().strip()
            tech = get_technical_context(clean_ticker)

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
            max_loss = round(total_shares * (pivot - stop_loss), 2)
            max_loss_pct = round((max_loss / total_capital) * 100, 2) if total_capital > 0 else None

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

                "state":new_state,

                "tier":tier,

                "hold_period":hold_period,

                "capital_used":capital_used,

                "capital_pct":capital_pct,

                "max_loss":max_loss,

                "max_loss_pct":max_loss_pct,

                "remaining_r":remaining_r,

                "t1_pct_away":t1_pct_away,

                "t2_pct_away":t2_pct_away

            })



        update_states(updates)



        # Invalidated setups (stop already breached, or a breakout that
        # failed after triggering) don't belong in a ranked "top
        # candidates" board - showing a full Entry/Exit-Strategy block for
        # a dead setup is misleading, not just noisy. They get a short,
        # separate, unranked list instead.
        active_board = [x for x in board if x["state"] not in INVALIDATED_STATES]

        invalidated_board = [x for x in board if x["state"] in INVALIDATED_STATES]

        active_board=sorted(

            active_board,

            key=lambda x:x["score"],

            reverse=True

        )



        duration=round(
            time.time()-start,
            2
        )


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


        print("\nSTATE DISTRIBUTION")


        for k,v in counters.items():

            print(
                f"{k:<22}: {v}"
            )


        print("\nTOP EXECUTION BOARD")


        for x in active_board[:10]:

            print("\n" + "-"*68)

            print(
                f"  {x['ticker']}  |  Score: {x['score']}"
            )

            print("-"*68)

            print(
                f"  Status       : {x['state']}"
            )

            print(
                f"  Price        : Rs{x['price']:.2f}  |  Pivot: Rs{x['pivot']:.2f}  |  Ext: {x['distance']:+.2f}%"
            )

            print(
                f"  RVOL         : {x['rvol']}x"
            )

            print("-"*68)

            print(
                f"  Entry        : Rs{x['price']:.2f}"
            )

            print(
                f"  Stop Loss    : Rs{x['stop_loss']:.2f}"
            )

            if x['t1_pct_away'] is not None:

                print(
                    f"  Target 1     : Rs{x['target_1']:.2f}  (+{x['t1_pct_away']}% away)"
                )

                print(
                    f"  Target 2     : Rs{x['target_2']:.2f}  (+{x['t2_pct_away']}% away)"
                )

                print(
                    f"  Remaining R  : {x['remaining_r']}x"
                )

            else:

                print(
                    f"  Target 1     : Rs{x['target_1']:.2f}"
                )

                print(
                    f"  Target 2     : Rs{x['target_2']:.2f}"
                )

                print(
                    f"  Remaining R  : N/A - stop already breached"
                )

            print("-"*68)

            print(
                f"  Units        : {x['qty']} shares"
            )

            if x['capital_pct'] is not None:

                print(
                    f"  Capital Used : Rs{x['capital_used']:,.0f}  ({x['capital_pct']}% of portfolio)"
                )

                print(
                    f"  Max Loss     : Rs{x['max_loss']:,.0f}  ({x['max_loss_pct']}% of capital)"
                )

            else:

                print(
                    f"  Capital Used : Rs{x['capital_used']:,.0f}"
                )

                print(
                    f"  Max Loss     : Rs{x['max_loss']:,.0f}"
                )

            print("-"*68)

            print(
                f"  Exit Strategy : Sell {x['sell_at_t1']} at T1 -> Sell {x['sell_at_t2']} at T2"
            )

            print("-"*68)

            print(
                f"  Tier         : {x['tier']}"
            )

            print(
                f"  Hold Period   : {x['hold_period']}"
            )

            read_text = get_read(x['state'], x['discount_pct'], x['vdry_ratio'], x['rvol'])

            print(
                f"  Read         : {read_text}"
            )


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

            for x in sorted(invalidated_board, key=lambda x: x.get("breach_pct") or 0, reverse=True):

                breach_str = f"{x['breach_pct']}% below stop" if x.get("breach_pct") is not None else "N/A"

                print(
                    f"  {x['ticker']:<12} {x['state']:<16} {breach_str}"
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