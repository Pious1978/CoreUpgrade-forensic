"""
Portfolio_Risk_Controller.py
------------------------------------------------

Controls portfolio exposure.

"""

import sqlite3

from core.config import DB_PATH



MAX_POSITIONS=10
MAX_CAPITAL_DEPLOYMENT=0.80



def check_portfolio_limits():


    conn=sqlite3.connect(DB_PATH)



    positions=conn.execute("""

    SELECT

    COUNT(*),

    SUM(entry_price*quantity)

    FROM positions

    WHERE status='OPEN'


    """).fetchone()



    conn.close()



    count=positions[0] or 0

    capital=positions[1] or 0



    return {


    "positions":count,

    "capital_used":capital,

    "allowed":

        count < MAX_POSITIONS


    }



if __name__=="__main__":

    print(check_portfolio_limits())
