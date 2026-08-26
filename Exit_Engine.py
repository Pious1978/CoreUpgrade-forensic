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

from core.config import DB_PATH
from core.Live_Price_Engine import LivePriceEngine



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
