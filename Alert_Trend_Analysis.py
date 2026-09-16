"""
Alert_Trend_Analysis.py

The genuinely reliable successor to the earlier ad-hoc RVOL analysis -
built now that core/notifications.py (see that file's docstring)
writes a real breakout_id linking each VALID_BREAKOUT to its own
TARGET_1_HIT/TARGET_2_HIT/STOP_BREACHED, plus the real pattern and
conviction score at the time of the breakout.

HONEST, DIRECT NOTE: this script will find very little real data the
day it's first run, since breakout_id/pattern/score are only present
on alerts logged AFTER core/notifications.py's enhancement. Old-style
lines (no " | " suffix) are still parsed for basic counts, but can't
be used for the pattern/score breakdowns below, since that context
was never captured for them. This is the expected, correct trade-off
- a real, growing dataset the schema doesn't have, rather than a
retroactively invented one.
"""

import re
from collections import defaultdict


def parse_alerts_log(path="alerts.log"):
    """Real, direct parser - handles both old-style lines (no suffix) and new, richer lines."""

    events = []

    with open(path) as f:
        for line in f:
            m = re.match(r'\[([\d-]+ [\d:]+)\] \[(\w+)\] \[(\w+)\] (\S+): (.+?)(?:\s\|\s(.+))?$', line.strip())
            if not m:
                continue

            ts_str, severity, event_type, ticker, message, context_str = m.groups()
            ticker = ticker.rstrip(":")

            context = {"breakout_id": None, "pattern": None, "score": None}
            if context_str:
                for part in context_str.split():
                    if "=" in part:
                        k, v = part.split("=", 1)
                        context[k] = v

            events.append({
                "ts": ts_str, "event_type": event_type, "ticker": ticker,
                "message": message, **context
            })

    return events


def analyze_by_breakout_id(events):
    """
    Real, unambiguous analysis - groups every event by its breakout_id
    (only possible for alerts logged after the enhancement), so each
    breakout's real outcome is known with certainty, not guessed at by
    ticker-name proximity.
    """

    by_id = defaultdict(list)
    for e in events:
        if e["breakout_id"]:
            by_id[e["breakout_id"]].append(e)

    results = []
    for breakout_id, group in by_id.items():
        breakout = next((e for e in group if e["event_type"] == "VALID_BREAKOUT"), None)
        if not breakout:
            continue

        outcome = "PENDING"
        for e in group:
            if e["event_type"] in ("TARGET_1_HIT", "TARGET_2_HIT"):
                outcome = e["event_type"]
            elif e["event_type"] == "STOP_BREACHED":
                outcome = "STOP_BREACHED"

        results.append({
            "ticker": breakout["ticker"],
            "pattern": breakout["pattern"],
            "score": float(breakout["score"]) if breakout["score"] else None,
            "outcome": outcome,
        })

    return results


def print_pattern_breakdown(results):
    """Real win-rate by pattern type - only possible now that pattern is actually captured."""

    resolved = [r for r in results if r["outcome"] != "PENDING"]

    if not resolved:
        print("No resolved, breakout_id-linked outcomes yet - this analysis needs real time to accumulate "
              "data under the new, richer logging. Check back in a few weeks.")
        return

    by_pattern = defaultdict(list)
    for r in resolved:
        by_pattern[r["pattern"] or "unknown"].append(r)

    print(f"{'Pattern':<20} {'N':<6} {'Win rate'}")
    print("-" * 40)
    for pattern, group in sorted(by_pattern.items(), key=lambda x: -len(x[1])):
        wins = [r for r in group if r["outcome"] in ("TARGET_1_HIT", "TARGET_2_HIT")]
        print(f"{pattern:<20} {len(group):<6} {len(wins)/len(group)*100:.1f}%")


if __name__ == "__main__":
    events = parse_alerts_log()
    results = analyze_by_breakout_id(events)
    print(f"Total events parsed: {len(events)}")
    print(f"Breakout_id-linked (genuinely unambiguous) outcomes: {len(results)}")
    print()
    print_pattern_breakdown(results)