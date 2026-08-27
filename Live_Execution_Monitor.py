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



# ================================================================
# MAIN ENGINE
# ================================================================


def run_live_monitor():


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

            # Scale-out plan: split evenly between Target 1 and Target 2.
            # This is a suggested default, not a discovered rule - adjust
            # the split ratio here if you want a different plan (e.g. sell
            # more at T1 and let a smaller remainder ride to T2).
            sell_at_t1 = total_shares // 2
            sell_at_t2 = total_shares - sell_at_t1
            clean_ticker = str(ticker).replace(".NS","").upper().strip()
            tech = get_technical_context(clean_ticker)

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

                "distance":distance,

                "rvol":rvol,

                "state":new_state

            })



        update_states(updates)



        board=sorted(

            board,

            key=lambda x:x["score"],

            reverse=True

        )



        duration=round(
            time.time()-start,
            2
        )


        print("\n"+"="*75)

        print(
            f"🎯 LIVE EXECUTION TERMINAL | {timestamp}"
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


        print("\nSTATE DISTRIBUTION")


        for k,v in counters.items():

            print(
                f"{k:<22}: {v}"
            )


        print("\nTOP EXECUTION BOARD")

        print(
        f"{'Stock':<10}{'Score':<7}{'Price':<9}{'Qty':<6}{'SL':<9}{'T1':<9}{'T2':<9}{'Qty@T1':<7}{'Qty@T2':<7}{'Dist':<8}{'RVOL':<6}{'Disc%':<8}{'VDry':<6}{'State'}"
        )

        print("-"*75)


        for x in board[:10]:

            disc_str = f"{x['discount_pct']:+.1f}%" if x['discount_pct'] is not None else "N/A"
            vdry_str = f"{x['vdry_ratio']}" if x['vdry_ratio'] is not None else "N/A"

            print(

            f"{x['ticker']:<10}"
            f"{x['score']:<7}"
            f"{x['price']:<9.2f}"
            f"{x['qty']:<6}"
            f"{x['stop_loss']:<9.2f}"
            f"{x['target_1']:<9.2f}"
            f"{x['target_2']:<9.2f}"
            f"{x['sell_at_t1']:<7}"
            f"{x['sell_at_t2']:<7}"
            f"{x['distance']:+.2f}%  "
            f"{x['rvol']:<6}"
            f"{disc_str:<8}"
            f"{vdry_str:<6}"
            f"{x['state']}"

            )

            read_text = get_read(x['state'], x['discount_pct'], x['vdry_ratio'], x['rvol'])
            print(f"          Read: {read_text}")
            print()



        print("-"*75)

        print(
            f"Cycle Time : {duration}s"
        )

        print(
            "Next Scan : 60 seconds"
        )

        print("="*75)



        time.sleep(60)



if __name__=="__main__":

    run_live_monitor()