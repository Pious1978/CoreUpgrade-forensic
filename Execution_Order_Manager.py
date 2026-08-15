"""
Execution_Order_Manager.py
------------------------------------------------------------

Paper Execution Layer

Consumes:
    trade_candidates

Creates:
    positions

No broker dependency.
Simulation execution only.
"""


import sqlite3
from datetime import datetime

from core.config import DB_PATH



# ==========================================================
# INITIALIZE POSITIONS TABLE
# ==========================================================

def init_positions_table():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS positions
    (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        ticker TEXT,

        entry_price REAL,

        quantity INTEGER,

        initial_stop REAL,

        current_stop REAL,

        target_1 REAL,

        target_2 REAL,

        status TEXT,

        entry_time TEXT,

        exit_price REAL,

        exit_reason TEXT

    )
    """)


    conn.commit()
    conn.close()



# ==========================================================
# LOAD APPROVED TRADE CANDIDATES
# ==========================================================

def load_trade_candidates(conn):

    query = """

    SELECT

        ticker,
        pivot,
        shares,
        stop_loss,
        target_1,
        target_2

    FROM trade_candidates

    WHERE
        shares > 0

    """

    return conn.execute(query).fetchall()



# ==========================================================
# CREATE PAPER POSITIONS
# ==========================================================

def execute_entries():


    conn = sqlite3.connect(DB_PATH)


    candidates = load_trade_candidates(conn)


    if not candidates:

        print("No trade candidates available.")
        conn.close()
        return 0



    cursor = conn.cursor()


    created = 0



    for row in candidates:


        (
            ticker,
            entry_price,
            quantity,
            stop_loss,
            target_1,
            target_2

        ) = row



        # -----------------------------------------
        # Duplicate protection
        # -----------------------------------------

        existing = cursor.execute(
            """

            SELECT COUNT(*)

            FROM positions

            WHERE ticker=?

            AND status='OPEN'

            """,
            (ticker,)

        ).fetchone()[0]



        if existing:

            continue



        cursor.execute(

        """

        INSERT INTO positions

        (

        ticker,

        entry_price,

        quantity,

        initial_stop,

        current_stop,

        target_1,

        target_2,

        status,

        entry_time

        )

        VALUES (?,?,?,?,?,?,?,?,?)

        """,

        (

        ticker,

        entry_price,

        quantity,

        stop_loss,

        stop_loss,

        target_1,

        target_2,

        "OPEN",

        datetime.now().isoformat()

        )

        )


        created += 1



    conn.commit()

    conn.close()


    return created



# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":


    print("""

============================================================
📈 PAPER EXECUTION ORDER MANAGER
============================================================

""")


    init_positions_table()


    created = execute_entries()


    print(
        f"Positions Created : {created}"
    )


    print("""

============================================================

""")
