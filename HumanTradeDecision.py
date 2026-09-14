"""
HumanTradeDecision.py

Addresses #90 - the missing object: this system's scanners can say
VALID_BREAKOUT with a real score, but the actual decision to trade it
or not is the operator's, and that decision was never being recorded
anywhere. Without it, six months from now there's no way to answer
"where does my own discretionary judgment add or subtract value from
the system?" - genuinely more useful than "does my scanner make money?"
alone.

Real schema, matching the architectural review's own spec exactly:
    decision_id
    trade_plan_id      - a real, persisted TradePlan_Builder.py ID
    decision           - ACCEPT / REJECT / DEFER
    decision_timestamp
    planned_quantity
    planned_entry
    reason
    operator_note

Deliberately simple to record - even a bare ACCEPT/REJECT with no
note is genuinely useful, per the architectural review's own point
that "we don't need to record our every thought."
"""

import sqlite3
from datetime import datetime

from core.config import DB_PATH

VALID_DECISIONS = ("ACCEPT", "REJECT", "DEFER")


def record_decision(trade_plan_id, decision, planned_quantity=None, planned_entry=None, reason=None, operator_note=None):
    """
    Real, direct recording of a human decision against a specific,
    real trade plan. Returns the new decision's own ID, or None if the
    trade_plan_id doesn't genuinely exist (a real, honest referential
    check, not a silent, dangling foreign key).
    """

    decision = decision.strip().upper()

    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}, got '{decision}'")

    conn = sqlite3.connect(DB_PATH)

    plan_exists = conn.execute(
        "SELECT 1 FROM trade_plans WHERE trade_plan_id = ?", (trade_plan_id,)
    ).fetchone()

    if not plan_exists:
        conn.close()
        return None

    conn.execute("""
        CREATE TABLE IF NOT EXISTS human_trade_decisions (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_plan_id INTEGER,
            decision TEXT,
            decision_timestamp TEXT,
            planned_quantity INTEGER,
            planned_entry REAL,
            reason TEXT,
            operator_note TEXT
        )
    """)

    cursor = conn.execute("""
        INSERT INTO human_trade_decisions
        (trade_plan_id, decision, decision_timestamp, planned_quantity, planned_entry, reason, operator_note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_plan_id,
        decision,
        datetime.now().isoformat(),
        planned_quantity,
        planned_entry,
        reason,
        operator_note,
    ))

    decision_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return decision_id


def get_decision_history(ticker=None):
    """
    Real, direct query joining human_trade_decisions back to
    trade_plans, so you can see what the system proposed alongside
    what you actually decided - the foundation for the "does my
    discretionary judgment add or subtract value" analysis the
    architectural review specifically called out.
    """

    import pandas as pd

    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT d.decision_id, p.ticker, p.as_of_date, d.decision,
               d.decision_timestamp, d.planned_quantity, d.planned_entry,
               d.reason, d.operator_note
        FROM human_trade_decisions d
        JOIN trade_plans p ON d.trade_plan_id = p.trade_plan_id
    """

    params = ()
    if ticker:
        query += " WHERE UPPER(p.ticker) = ?"
        params = (ticker.upper(),)

    query += " ORDER BY d.decision_timestamp DESC"

    try:
        df = pd.read_sql(query, conn, params=params)
    except Exception:
        df = pd.DataFrame()

    conn.close()
    return df


if __name__ == "__main__":
    trade_plan_id = int(input("Trade Plan ID: ").strip())
    decision = input("Decision (ACCEPT/REJECT/DEFER): ").strip()
    reason = input("Reason (optional, blank to skip): ").strip() or None

    decision_id = record_decision(trade_plan_id, decision, reason=reason)

    if decision_id:
        print(f"[+] Recorded decision #{decision_id}: {decision.upper()} on trade plan #{trade_plan_id}")
    else:
        print(f"[!] Trade plan #{trade_plan_id} doesn't exist - nothing recorded.")