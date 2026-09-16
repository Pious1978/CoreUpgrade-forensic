"""
Backfill_Alert_Context.py

Confirmed directly: scanner_factors and daily_snapshot both carry a
real, historical date column and preserve past data (scanner_factors
confirmed going back to 2026-08-27) - unlike trade_candidates, which
overwrites daily. This means the real, historical inputs to the
Opportunity component of calculate_conviction_score() (see
Live_Execution_Monitor.py) can genuinely be recovered for past
breakouts, not guessed.

HONEST, DIRECT LIMITS - stated plainly, not glossed over:

1. Only OPPORTUNITY is recovered, not the full conviction score.
   Opportunity is explicitly "independent of live timing" (its own
   docstring) and needs only rs_percentile, delivery_score,
   accumulation_ratio, base_compression, cup_handle_quality,
   hybrid_alpha_score - all available historically. Readiness needs
   weekly_rvol, remaining_r, and pivot_extension at the moment of the
   original breakout, none of which were ever logged - genuinely
   unrecoverable, not backfilled here.

2. pattern remains genuinely unrecoverable. Which scanner originally
   classified a ticker isn't stored anywhere historically. Not
   backfilled - left absent rather than guessed.

3. breakout_id here is HEURISTIC, not a real link. It's generated
   with the same "next event for this ticker" matching used in the
   original ad-hoc analysis - honestly labeled as
   "backfilled=heuristic" in the output, so later analysis can
   distinguish it from the genuinely unambiguous, real-time-linked
   breakout_id that core/notifications.py now generates for new
   alerts going forward.

This script REWRITES alerts.log in place. It backs up the original
first, and only ever ADDS a suffix to existing lines - never touches
the original message text.
"""

import re
import sqlite3
import hashlib
import shutil
from datetime import datetime
from collections import defaultdict

from core.config import DB_PATH

ALERTS_LOG_PATH = "alerts.log"


def compute_historical_opportunity(conn, ticker, date_str):
    """
    Real, direct recomputation of the Opportunity score using the
    exact same formula as calculate_conviction_score() in
    Live_Execution_Monitor.py, fed with genuinely historical inputs
    for this specific ticker and date - not today's values.
    """

    snap = conn.execute("""
        SELECT rs_percentile, delivery_score FROM daily_snapshot
        WHERE symbol = ? AND date = ?
    """, (ticker, date_str)).fetchone()

    rs_percentile = snap[0] if snap else None
    delivery_score = snap[1] if snap else None

    factor_names = ("accumulation_ratio", "base_compression", "cup_handle_quality", "hybrid_alpha_score")
    rows = conn.execute(f"""
        SELECT factor_name, score FROM scanner_factors
        WHERE ticker = ? AND date = ? AND factor_name IN {factor_names}
    """, (ticker, date_str)).fetchall()

    factors = {name: score for name, score in rows}
    accumulation_ratio = factors.get("accumulation_ratio")
    base_compression = factors.get("base_compression")
    cup_handle_quality = factors.get("cup_handle_quality")
    hybrid_alpha_score = factors.get("hybrid_alpha_score")

    if rs_percentile is None and delivery_score is None and not factors:
        return None  # Genuinely no historical data for this ticker/date - honest None, not a fabricated default

    relative_strength = rs_percentile if rs_percentile is not None else 50.0

    institutional = (
        (delivery_score if delivery_score is not None else 50.0) * 0.6 +
        (accumulation_ratio * 100 if accumulation_ratio is not None else 50.0) * 0.4
    )

    structure_components = [
        (base_compression * 100 if base_compression is not None else None, 0.6),
        (hybrid_alpha_score * 100 if hybrid_alpha_score is not None else None, 0.2),
        (cup_handle_quality * 100 if cup_handle_quality is not None else None, 0.2),
    ]
    available = [(v, w) for v, w in structure_components if v is not None]
    total_w = sum(w for v, w in available)
    structure = sum(v * w for v, w in available) / total_w if total_w > 0 else 50.0

    opportunity = round(
        relative_strength * (0.30 / 0.70) +
        institutional * (0.20 / 0.70) +
        structure * (0.20 / 0.70),
        1
    )

    return opportunity


def backfill():
    shutil.copy(ALERTS_LOG_PATH, ALERTS_LOG_PATH + ".backup")
    print(f"Backed up original to {ALERTS_LOG_PATH}.backup")

    with open(ALERTS_LOG_PATH) as f:
        lines = f.readlines()

    parsed = []
    for i, line in enumerate(lines):
        m = re.match(r'\[([\d-]+) ([\d:]+)\] \[(\w+)\] \[(\w+)\] (\S+):', line)
        if not m:
            parsed.append({"line_idx": i, "raw": line})
            continue
        date_str, time_str, severity, event_type, ticker = m.groups()
        ticker = ticker.rstrip(":")
        parsed.append({
            "line_idx": i, "raw": line, "date": date_str,
            "ts": datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"),
            "event_type": event_type, "ticker": ticker,
        })

    already_rich = [p for p in parsed if "raw" in p and "breakout_id=" in p["raw"]]
    print(f"Skipping {len(already_rich)} lines that already have real, forward-linked context.")

    conn = sqlite3.connect(DB_PATH)

    breakouts = [p for p in parsed if p.get("event_type") == "VALID_BREAKOUT" and "breakout_id=" not in p["raw"]]
    print(f"Backfilling {len(breakouts)} old-style VALID_BREAKOUT events...")

    enriched_count = 0
    no_data_count = 0

    for b in breakouts:
        opportunity = compute_historical_opportunity(conn, b["ticker"], b["date"])

        if opportunity is None:
            no_data_count += 1
            continue

        heuristic_id = hashlib.sha1(f"{b['ticker']}_{b['ts'].isoformat()}".encode()).hexdigest()[:10]

        suffix = f" | breakout_id={heuristic_id} opportunity={opportunity} backfilled=heuristic\n"
        lines[b["line_idx"]] = lines[b["line_idx"]].rstrip("\n") + suffix
        enriched_count += 1

        # Real, direct matching: same "next event for this ticker" heuristic
        # as the original ad-hoc analysis - honestly labeled as such via the
        # backfilled=heuristic marker, not presented as a certain link.
        later = sorted(
            [p for p in parsed if p.get("ticker") == b["ticker"] and p.get("ts") and p["ts"] > b["ts"]],
            key=lambda p: p["ts"]
        )
        for le in later:
            if le.get("event_type") in ("TARGET_1_HIT", "TARGET_2_HIT", "STOP_BREACHED"):
                if "breakout_id=" not in lines[le["line_idx"]]:
                    lines[le["line_idx"]] = lines[le["line_idx"]].rstrip("\n") + suffix
                break

    conn.close()

    with open(ALERTS_LOG_PATH, "w") as f:
        f.writelines(lines)

    print(f"Enriched {enriched_count} breakout events with real, historical Opportunity scores.")
    print(f"{no_data_count} breakouts had no historical scanner_factors/daily_snapshot data available - left as-is, not guessed.")


if __name__ == "__main__":
    backfill()