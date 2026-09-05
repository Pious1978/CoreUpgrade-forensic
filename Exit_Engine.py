"""
Exit_Engine.py
--------------------------------------------------

Institutional exit decision engine.

Rules:

1. Stop loss
2. Failed breakout
3. Target booking
4. Trend violation

"""

import sqlite3
from datetime import datetime

from core.config import DB_PATH, PARQUET_CACHE_DIR
from core.Live_Price_Engine import LivePriceEngine

MIN_PROGRESS_FRACTION = 0.5  # require at least half a risk-unit of progress
MAX_SESSIONS_WITHOUT_PROGRESS = 5  # matches the user's real example (4+ stagnant days)


def check_time_stop(ticker, entry_price, initial_stop, entry_time, current_price):
    """
    #71 - Real, direct feedback: "never hits stop, never hits target...
    what does the system do?" Position_Manager/Exit_Engine previously
    had no answer for a stock that simply goes nowhere. Uses
    entry_price - initial_stop as the real risk unit (this is already
    1.5xATR at entry, per Risk_Positioning_Engine.py's real formula -
    reused directly rather than recomputing ATR separately). Counts
    REAL trading days from parquet_cache, matching the same established
    pattern as #65/#68, not calendar days.
    """

    import os
    import pandas as pd

    path = os.path.join(PARQUET_CACHE_DIR, f"{ticker.upper()}.parquet")

    if not os.path.exists(path):
        return False, None

    try:
        df = pd.read_parquet(path)
        df.columns = [str(c).lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        entry_dt = pd.Timestamp(entry_time)
        sessions_since_entry = int((df["date"] > entry_dt).sum())

        if sessions_since_entry < MAX_SESSIONS_WITHOUT_PROGRESS:
            return False, sessions_since_entry  # still within the grace period

        risk_per_share = entry_price - initial_stop

        if risk_per_share <= 0:
            return False, sessions_since_entry

        progress = current_price - entry_price
        required_progress = MIN_PROGRESS_FRACTION * risk_per_share

        if progress < required_progress:
            return True, sessions_since_entry

        return False, sessions_since_entry

    except Exception:
        return False, None



def process_exits():


    conn=sqlite3.connect(DB_PATH)


    positions=conn.execute("""

    SELECT *

    FROM positions

    WHERE status='OPEN'

    """).fetchall()



    cols=[
    x[1]
    for x in conn.execute(
        "PRAGMA table_info(positions)"
    )
    ]


    conn.close()



    for row in positions:


        p=dict(zip(cols,row))


        quote=LivePriceEngine.get_live_quote(
            p["ticker"]
        )


        price=quote["ltp"]



        if price<=0:

            continue



        reason=None



        if price <= p["current_stop"]:

            reason="STOP_LOSS"



        elif price >= p["target_2"]:

            reason="TARGET_2"



        elif price >= p["target_1"]:

            reason="TARGET_1"


        # #71 - real time stop, checked only if stop/target haven't
        # already fired (those take priority - a genuinely stagnant
        # position that then hits its stop should still exit as
        # STOP_LOSS, not get relabeled).
        if not reason and p.get("entry_time"):

            time_stop_triggered, sessions = check_time_stop(
                p["ticker"], p["entry_price"], p["initial_stop"], p["entry_time"], price
            )

            if time_stop_triggered:
                reason = "TIME_STOP"



        if reason:


            conn=sqlite3.connect(DB_PATH)

            conn.execute("""

            UPDATE positions

            SET

            status='CLOSED',

            exit_price=?,

            exit_reason=?

            WHERE ticker=?

            AND status='OPEN'


            """,

            (

            price,

            reason,

            p["ticker"]

            ))


            conn.commit()

            conn.close()



if __name__=="__main__":

    process_exits()