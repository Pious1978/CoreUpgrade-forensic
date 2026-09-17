"""
Regime_Sector_Outcome_Analysis.py

Real, direct analysis of market regime and sector strength on the days
wins and losses occurred - both confirmed as genuinely, historically
preserved (market_regime keys on date; sector_strength_ranking is
append-only, confirmed directly from Sector_Strength_Ranker.py's own
write logic: DELETE for that specific run_date only, then INSERT...
if_exists="append" - not overwritten across dates).

Joins against the same breakout_id-linked outcomes Backfill_Alert_Context.py
and Alert_Trend_Analysis.py already established - reuses that real,
unambiguous linking rather than re-deriving it.
"""

import re
import sqlite3
from collections import defaultdict

from core.config import DB_PATH
from core.sector_map import get_sector


def parse_linked_outcomes(path="alerts.log"):
    """Real, direct reuse of the same breakout_id-linked parsing already established."""

    events = []
    with open(path) as f:
        for line in f:
            m = re.match(r'\[([\d-]+) ([\d:]+)\] \[\w+\] \[(\w+)\] (\S+): (.+?)(?:\s\|\s(.+))?$', line.strip())
            if not m:
                continue
            date_str, time_str, event_type, ticker, message, context_str = m.groups()
            ticker = ticker.rstrip(":")
            context = {"breakout_id": None}
            if context_str:
                for part in context_str.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        context[k] = v
            events.append({"date": date_str, "event_type": event_type, "ticker": ticker, **context})

    by_id = defaultdict(list)
    for e in events:
        if e["breakout_id"]:
            by_id[e["breakout_id"]].append(e)

    results = []
    for bid, group in by_id.items():
        breakout = next((e for e in group if e["event_type"] == "VALID_BREAKOUT"), None)
        if not breakout:
            continue
        outcome = "PENDING"
        for e in group:
            if e["event_type"] in ("TARGET_1_HIT", "TARGET_2_HIT"):
                outcome = e["event_type"]
            elif e["event_type"] == "STOP_BREACHED":
                outcome = "STOP_BREACHED"
        results.append({"ticker": breakout["ticker"], "date": breakout["date"], "outcome": outcome})

    return [r for r in results if r["outcome"] != "PENDING"]


def get_regime_for_date(conn, date_str):
    row = conn.execute("SELECT regime FROM market_regime WHERE date = ?", (date_str,)).fetchone()
    return row[0] if row else None


def get_sector_rank_for_date(conn, sector, date_str):
    """
    Real, direct rank computation - sector_strength_ranking doesn't
    store rank directly, only the raw liquidity_weighted_rs score, so
    this reconstructs the same ranking Stock_Lookup.py's own display
    uses (sorted descending by that score) for this specific date.
    """

    rows = conn.execute("""
        SELECT sector, liquidity_weighted_rs FROM sector_strength_ranking
        WHERE run_date = ?
        ORDER BY liquidity_weighted_rs DESC
    """, (date_str,)).fetchall()

    if not rows:
        return None, None, None

    total = len(rows)
    for i, (s, rs) in enumerate(rows, start=1):
        if s == sector:
            return i, total, rs

    return None, total, None


def run():
    outcomes = parse_linked_outcomes()
    print(f"Resolved, genuinely linked outcomes to analyze: {len(outcomes)}")

    conn = sqlite3.connect(DB_PATH)

    enriched = []
    for o in outcomes:
        regime = get_regime_for_date(conn, o["date"])
        sector = get_sector(o["ticker"])
        rank, total, rs = get_sector_rank_for_date(conn, sector, o["date"])
        enriched.append({**o, "regime": regime, "sector": sector, "sector_rank": rank, "sector_total": total, "sector_rs": rs})

    conn.close()

    wins = [e for e in enriched if e["outcome"] in ("TARGET_1_HIT", "TARGET_2_HIT")]
    losses = [e for e in enriched if e["outcome"] == "STOP_BREACHED"]

    print()
    print("=== MARKET REGIME on win days vs loss days ===")
    win_regimes = defaultdict(int)
    loss_regimes = defaultdict(int)
    for w in wins:
        win_regimes[w["regime"] or "unknown"] += 1
    for l in losses:
        loss_regimes[l["regime"] or "unknown"] += 1
    print(f"Wins ({len(wins)}):  {dict(win_regimes)}")
    print(f"Losses ({len(losses)}): {dict(loss_regimes)}")

    print()
    print("=== SECTOR RANK (1 = strongest) on win days vs loss days ===")
    win_ranks = [w["sector_rank"] for w in wins if w["sector_rank"] is not None]
    loss_ranks = [l["sector_rank"] for l in losses if l["sector_rank"] is not None]
    if win_ranks:
        print(f"Wins:   avg sector rank {sum(win_ranks)/len(win_ranks):.1f} of ~{wins[0]['sector_total']} (n={len(win_ranks)})")
    else:
        print("Wins: no sector rank data available")
    if loss_ranks:
        print(f"Losses: avg sector rank {sum(loss_ranks)/len(loss_ranks):.1f} of ~{losses[0]['sector_total']} (n={len(loss_ranks)})")
    else:
        print("Losses: no sector rank data available")

    print()
    print("=== Detail: each win/loss with its real regime and sector rank ===")
    for e in enriched:
        rank_str = f"#{e['sector_rank']}/{e['sector_total']}" if e['sector_rank'] else "N/A"
        print(f"{e['outcome']:<16} {e['ticker']:<14} {e['date']:<12} regime={e['regime'] or 'unknown':<20} sector={e['sector']:<20} rank={rank_str}")


if __name__ == "__main__":
    run()