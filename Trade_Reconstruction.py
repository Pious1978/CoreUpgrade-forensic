"""
Trade_Reconstruction.py

Addresses #95 - the full per-trade reconstruction chain:
TradePlan -> HumanTradeDecision -> ActualTrade -> real, eventual
Outcome, each piece independently versioned and queryable, now tied
together into one reconstructed story.

HONEST, DIRECT NOTE ON SCOPE: this system already has a real, working
outcome-recording mechanism - Trade_Journal.py's own trade_journal
table, which carries entry AND exit (realized_pnl, r_multiple,
exit_price, exit_date) in a single row. #95 does not need a new
"OutcomeArtifact" table invented from scratch - the real, missing
piece was purely the LINK between the new chain (built tonight:
trade_plans / human_trade_decisions / actual_trades) and this
pre-existing, separate system. There is no formal foreign key between
them, since ActualTrade.py and Trade_Journal.py were never connected
- this reconstructs the link with a best-effort match (same ticker,
entry date within a few days of the actual fill), and says so
directly rather than presenting it as more certain than it is.
"""

import sqlite3
import json
from datetime import datetime, timedelta

from core.config import DB_PATH
from Event_Log import log_event


def find_matching_journal_entry(ticker, execution_timestamp, tolerance_days=3):
    """
    Real, honest best-effort match to Trade_Journal.py's separate
    trade_journal table - no formal foreign key exists between the two
    systems, so this matches on the two things that should genuinely
    agree: the same ticker, and an entry_date within a few real days
    of the actual fill's own timestamp.
    """

    conn = sqlite3.connect(DB_PATH)

    exec_date = datetime.fromisoformat(execution_timestamp).date()
    low = (exec_date - timedelta(days=tolerance_days)).isoformat()
    high = (exec_date + timedelta(days=tolerance_days)).isoformat()

    row = conn.execute("""
        SELECT id, status, entry_price, entry_date, exit_price, exit_date,
               realized_pnl, realized_pct, r_multiple
        FROM trade_journal
        WHERE UPPER(ticker) = ? AND entry_date BETWEEN ? AND ?
        ORDER BY entry_date ASC
        LIMIT 1
    """, (ticker.upper(), low, high)).fetchone()

    conn.close()

    if not row:
        return None

    return {
        "journal_id": row[0],
        "status": row[1],
        "entry_price": row[2],
        "entry_date": row[3],
        "exit_price": row[4],
        "exit_date": row[5],
        "realized_pnl": row[6],
        "realized_pct": row[7],
        "r_multiple": row[8],
    }


def reconstruct_trade(trade_plan_id):
    """
    Real, complete reconstruction of a specific trade's entire story,
    from the original research evidence through to its real, eventual
    outcome (if closed) - the genuine payoff #95 asks for.
    """

    conn = sqlite3.connect(DB_PATH)

    plan_row = conn.execute(
        "SELECT ticker, as_of_date, plan_json FROM trade_plans WHERE trade_plan_id = ?",
        (trade_plan_id,)
    ).fetchone()

    if not plan_row:
        conn.close()
        return None

    ticker, as_of_date, plan_json = plan_row
    plan = json.loads(plan_json)

    decision_row = conn.execute(
        "SELECT decision_id, decision, decision_timestamp, reason FROM human_trade_decisions WHERE trade_plan_id = ?",
        (trade_plan_id,)
    ).fetchone()

    story = {
        "trade_plan_id": trade_plan_id,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "trade_plan": plan,
        "human_decision": None,
        "actual_trade": None,
        "outcome": None,
    }

    if not decision_row:
        conn.close()
        return story

    decision_id, decision, decision_timestamp, reason = decision_row
    story["human_decision"] = {
        "decision_id": decision_id,
        "decision": decision,
        "decision_timestamp": decision_timestamp,
        "reason": reason,
    }

    if decision != "ACCEPT":
        conn.close()
        return story

    trade_row = conn.execute(
        "SELECT trade_id, broker, actual_entry, actual_quantity, execution_timestamp FROM actual_trades WHERE decision_id = ?",
        (decision_id,)
    ).fetchone()

    conn.close()

    if not trade_row:
        return story

    trade_id, broker, actual_entry, actual_quantity, execution_timestamp = trade_row
    story["actual_trade"] = {
        "trade_id": trade_id,
        "broker": broker,
        "actual_entry": actual_entry,
        "actual_quantity": actual_quantity,
        "execution_timestamp": execution_timestamp,
    }

    outcome = find_matching_journal_entry(ticker, execution_timestamp)
    story["outcome"] = outcome

    if outcome and outcome["status"] == "CLOSED":
        log_event("TRADE_STORY_CLOSED", ticker, {
            "trade_plan_id": trade_plan_id,
            "journal_id": outcome["journal_id"],
            "realized_pnl": outcome["realized_pnl"],
            "r_multiple": outcome["r_multiple"],
        })

    return story


def print_trade_story(trade_plan_id):
    """Human-readable rendering of a trade's complete, real, reconstructed story."""

    story = reconstruct_trade(trade_plan_id)

    if not story:
        print(f"No trade plan found with ID {trade_plan_id}.")
        return

    print()
    print("=" * 72)
    print(f"TRADE STORY: {story['ticker']}  (Trade Plan #{story['trade_plan_id']}, {story['as_of_date']})")
    print("=" * 72)

    print(f"\n1. TRADE PLAN")
    print(f"   Pattern: {story['trade_plan']['setup']['pattern']}  |  "
          f"Composite score: {story['trade_plan']['provenance']['composite_score']}  |  "
          f"Factor registry: {story['trade_plan']['provenance'].get('factor_registry_version', 'unrecorded')}")
    print(f"   Thesis: {story['trade_plan']['trade_thesis']}")

    if not story["human_decision"]:
        print("\n2. HUMAN DECISION: none recorded yet.")
        print("=" * 72)
        return

    d = story["human_decision"]
    print(f"\n2. HUMAN DECISION: {d['decision']}  ({d['decision_timestamp']})")
    if d["reason"]:
        print(f"   Reason: {d['reason']}")

    if d["decision"] != "ACCEPT":
        print("\n(Rejected/deferred - no execution to reconstruct further.)")
        print("=" * 72)
        return

    if not story["actual_trade"]:
        print("\n3. ACTUAL TRADE: accepted, but no fill recorded yet.")
        print("=" * 72)
        return

    a = story["actual_trade"]
    planned_entry = story["trade_plan"]["entry_plan"]["pivot"]
    slippage_pct = round((a["actual_entry"] - planned_entry) / planned_entry * 100, 2) if planned_entry else None
    print(f"\n3. ACTUAL TRADE: {a['actual_quantity']} shares @ Rs{a['actual_entry']} via {a['broker']}"
          f" ({a['execution_timestamp']})")
    if slippage_pct is not None:
        print(f"   Execution slippage vs plan: {slippage_pct:+.2f}%")

    if not story["outcome"]:
        print("\n4. OUTCOME: no matching Trade_Journal.py record found "
              "(best-effort match on ticker + entry date - may not have been logged there, or the match failed).")
        print("=" * 72)
        return

    o = story["outcome"]
    if o["status"] != "CLOSED":
        print(f"\n4. OUTCOME: still open (Trade_Journal.py status: {o['status']}).")
    else:
        print(f"\n4. OUTCOME: CLOSED - realized P&L Rs{o['realized_pnl']} "
              f"({o['realized_pct']}%), {o['r_multiple']}R, exited Rs{o['exit_price']} on {o['exit_date']}")

    print("=" * 72)


if __name__ == "__main__":
    trade_plan_id = int(input("Trade Plan ID: ").strip())
    print_trade_story(trade_plan_id)