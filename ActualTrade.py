"""
ActualTrade.py

Addresses #91 - the final link in the chain: TradePlan -> what the
system proposed. HumanTradeDecision -> whether you chose to trade it.
ActualTrade -> what genuinely happened at the broker. This system has
no OMS/broker connectivity (confirmed inert in the original forensic
investigation), so this is recorded manually, matching the real
manual-trading lifecycle: TradePlan -> HumanTradeDecision -> you
execute in your broker terminal -> record what actually happened here.

Real schema, matching the architectural review's own spec exactly:
    trade_id
    decision_id
    broker
    broker_order_reference
    actual_entry
    actual_quantity
    execution_timestamp

The real, direct value this unlocks: comparing the TradePlan's planned
entry (the pivot) against what you actually got filled at - the exact
"execution failure" example the architectural review gave: "System:
breakout at Rs2,699. You: entered at Rs2,760 because you were late.
The research was right; execution was poor." Without this comparison,
that failure mode is invisible - a loss just looks like a loss,
regardless of whether the setup was wrong or the execution was.
"""

import sqlite3
import json

from core.config import DB_PATH


def record_actual_trade(decision_id, broker, actual_entry, actual_quantity,
                         broker_order_reference=None, execution_timestamp=None):
    """
    Real, direct recording of an actual fill against a specific,
    real decision. Requires the decision to genuinely exist AND to
    have been ACCEPT - recording an actual trade against a REJECT or
    DEFER decision would be a real, catchable logical inconsistency,
    not something to silently allow.
    """

    from datetime import datetime

    conn = sqlite3.connect(DB_PATH)

    decision_row = conn.execute(
        "SELECT decision FROM human_trade_decisions WHERE decision_id = ?", (decision_id,)
    ).fetchone()

    if not decision_row:
        conn.close()
        return None, "decision_id does not exist"

    if decision_row[0] != "ACCEPT":
        conn.close()
        return None, f"decision was {decision_row[0]}, not ACCEPT - can't record an actual trade against it"

    conn.execute("""
        CREATE TABLE IF NOT EXISTS actual_trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id INTEGER,
            broker TEXT,
            broker_order_reference TEXT,
            actual_entry REAL,
            actual_quantity INTEGER,
            execution_timestamp TEXT
        )
    """)

    cursor = conn.execute("""
        INSERT INTO actual_trades
        (decision_id, broker, broker_order_reference, actual_entry, actual_quantity, execution_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        decision_id,
        broker,
        broker_order_reference,
        actual_entry,
        actual_quantity,
        execution_timestamp or datetime.now().isoformat(),
    ))

    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return trade_id, None


def compute_execution_quality(trade_id):
    """
    Real, direct reconciliation: joins actual_trades back through
    human_trade_decisions to trade_plans, comparing the ORIGINAL
    planned entry (the pivot) against what was actually filled -
    the exact "execution failure" signal the architectural review
    asked for, computed directly rather than left as an unanswerable
    question.
    """

    conn = sqlite3.connect(DB_PATH)

    row = conn.execute("""
        SELECT a.actual_entry, a.actual_quantity, p.plan_json, p.ticker
        FROM actual_trades a
        JOIN human_trade_decisions d ON a.decision_id = d.decision_id
        JOIN trade_plans p ON d.trade_plan_id = p.trade_plan_id
        WHERE a.trade_id = ?
    """, (trade_id,)).fetchone()

    conn.close()

    if not row:
        return None

    actual_entry, actual_quantity, plan_json, ticker = row
    plan = json.loads(plan_json)
    planned_entry = plan.get("entry_plan", {}).get("pivot")

    if planned_entry is None or planned_entry <= 0:
        return {"ticker": ticker, "reason": "No planned entry (pivot) found to compare against."}

    slippage_pct = round((actual_entry - planned_entry) / planned_entry * 100, 2)

    return {
        "ticker": ticker,
        "planned_entry": planned_entry,
        "actual_entry": actual_entry,
        "actual_quantity": actual_quantity,
        "slippage_pct": slippage_pct,
        "reason": f"Planned entry Rs{planned_entry}, actual fill Rs{actual_entry} "
                  f"({slippage_pct:+.2f}% {'worse' if slippage_pct > 0 else 'better'} than planned)",
    }


if __name__ == "__main__":
    decision_id = int(input("Decision ID (must be ACCEPT): ").strip())
    broker = input("Broker: ").strip()
    actual_entry = float(input("Actual entry price: ").strip())
    actual_quantity = int(input("Actual quantity: ").strip())
    broker_order_reference = input("Broker order reference (optional): ").strip() or None

    trade_id, error = record_actual_trade(decision_id, broker, actual_entry, actual_quantity, broker_order_reference)

    if trade_id:
        print(f"[+] Recorded actual trade #{trade_id}")
        quality = compute_execution_quality(trade_id)
        if quality and "slippage_pct" in quality:
            print(f"[+] {quality['reason']}")
    else:
        print(f"[!] {error}")