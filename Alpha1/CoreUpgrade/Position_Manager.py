"""
Position_Manager.py
--------------------------------------------------

Institutional position lifecycle manager.

Handles:

- trailing stop
- profit protection
- stop movement

"""

import sqlite3
from datetime import datetime

from core.config import DB_PATH
from Live_Price_Engine import LivePriceEngine



TRAILING_START = 10

TRAILING_DISTANCE = 5



def update_positions():


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



    updates=[]



    for row in positions:


        p=dict(zip(cols,row))


        quote=LivePriceEngine.get_live_quote(
            p["ticker"]
        )


        price=quote["ltp"]



        if price<=0:

            continue



        profit_pct=(

            (price-p["entry_price"])
            /
            p["entry_price"]

        )*100



        new_stop=p["current_stop"]



        # move stop after +10%

        if profit_pct>=TRAILING_START:


            new_stop=max(

                p["current_stop"],

                price*(1-TRAILING_DISTANCE/100)

            )



        updates.append(

        (

        new_stop,

        p["ticker"]

        )

        )



    if updates:


        conn=sqlite3.connect(DB_PATH)


        conn.executemany("""

        UPDATE positions

        SET current_stop=?

        WHERE ticker=?

        AND status='OPEN'

        """,

        updates)



        conn.commit()

        conn.close()



if __name__=="__main__":

    update_positions()
