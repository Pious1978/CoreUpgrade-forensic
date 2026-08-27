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


from core.config import DB_PATH
from core.Live_Price_Engine import LivePriceEngine
from core.Execution_State_Machine import evaluate_trade



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