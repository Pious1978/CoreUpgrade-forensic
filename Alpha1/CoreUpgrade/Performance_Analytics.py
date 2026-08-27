"""
Performance_Analytics.py
------------------------------------------------

Trade performance journal.

"""

import sqlite3

from core.config import DB_PATH



def generate_report():


    conn=sqlite3.connect(DB_PATH)


    df=conn.execute("""

    SELECT

    ticker,

    entry_price,

    exit_price,

    exit_reason


    FROM positions

    WHERE status='CLOSED'


    """).fetchall()


    conn.close()



    total=len(df)

    wins=0


    for x in df:


        if x[2]>x[1]:

            wins+=1



    winrate=(wins/total*100) if total else 0



    print("============================")

    print("TRADE PERFORMANCE")

    print("============================")

    print("Trades:",total)

    print("Win Rate:",round(winrate,2),"%")



if __name__=="__main__":

    generate_report()
