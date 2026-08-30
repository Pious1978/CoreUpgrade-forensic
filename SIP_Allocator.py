"""
SIP_Allocator.py

Profile-based monthly SIP (systematic investment) allocation - adapted
from Alpha1's real long_planner.py (MasterLongPlanner class), which
unified three separate profile-specific scripts (Compounders/Growth/
HighRisk) into one class with profile configs.

HONEST SCOPING NOTE: the original design assumed three separate
scanners, one per profile (a genuine, hand-curated Compounder
watchlist, a different Growth watchlist, a different HighRisk
watchlist). We only have real scoring for the Compounder tier today
(Compounder_Scanner.py's quality-gated, z-score-ranked output) - Growth
and HighRisk would need their own, different scanning criteria
(momentum-focused for Growth; smaller-cap, higher-beta for HighRisk)
that don't exist yet. This script builds the real, generic allocation
mechanism (profile configs, weighted sizing by score, market-condition
awareness, leftover-cash tracking) and applies it to the Compounder
tier specifically - not a false claim of replicating all three profiles
on top of one scanner.

Consumes: compounder_candidates (written by Compounder_Scanner.py)
Depends on: the same Monday fundamentals coverage check as
Compounder_Scanner.py itself - this is allocation logic sitting on top
of that scanner's output, so it's only as good as that output is.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

from core.config import DB_PATH, BASE_DIR
from core.excel_utils import save_excel_with_retry

PROFILES = {
    "Compounder": {"max_pos_size": 0.15, "stop_loss": 0.20},
    # Growth and HighRisk profiles are defined here for when their own
    # scanners exist, but aren't usable yet - no real candidate source
    # feeds them today.
    "Growth": {"max_pos_size": 0.08, "stop_loss": 0.10},
    "HighRisk": {"max_pos_size": 0.03, "stop_loss": 0.05},
}


def get_current_regime():
    """Reuses the same real regime read pattern already established in
    Pipeline_DAG_Executor.py and Risk_Positioning_Engine.py."""

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT regime FROM market_regime ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return row[0] if row else "NEUTRAL"
    except Exception:
        return "NEUTRAL"


def load_compounder_candidates():
    """Real candidates from Compounder_Scanner.py's own output - not a
    hardcoded watchlist."""

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT ticker, score, sector, sector_warning
            FROM compounder_candidates
            WHERE date = (SELECT MAX(date) FROM compounder_candidates)
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"[-] Could not load compounder_candidates: {e}")
        return pd.DataFrame()


def calculate_sip_allocation(candidates_df, sip_budget, regime, profile="Compounder"):
    """
    Weighted allocation by score (real v9 methodology), capped at the
    profile's max position size as a share of THIS MONTH'S SIP budget -
    not total portfolio, since this is a recurring monthly deployment
    decision, not a full position-sizing calculation. Leftover,
    unallocated cash is tracked explicitly rather than silently lost -
    a real, expected outcome when few candidates or a tight cap leave
    some of the budget undeployed this month.
    """

    config = PROFILES[profile]

    # Market-condition awareness: a genuine downturn is a real buying
    # opportunity for quality names, not just a reason to hold back -
    # deploy more of this month's budget rather than less. Driven by
    # our own real regime engine, not a manually-typed "Cheap" flag.
    if regime in ("BEAR", "DISTRIBUTION"):
        adjusted_budget = sip_budget * 1.2
        regime_note = f"Regime is {regime} - budget boosted 20% (genuine buying opportunity)"
    else:
        adjusted_budget = sip_budget
        regime_note = f"Regime is {regime} - budget unchanged"

    if candidates_df.empty:
        return [], adjusted_budget, adjusted_budget, regime_note

    total_score = sum(abs(s) + 1 for s in candidates_df["score"])

    allocations = []
    total_allocated = 0.0

    for _, row in candidates_df.iterrows():

        weight = (abs(row["score"]) + 1) / total_score
        allocation = adjusted_budget * weight

        max_allowed = adjusted_budget * config["max_pos_size"]
        allocation = min(allocation, max_allowed)

        allocations.append({
            "ticker": row["ticker"],
            "score": row["score"],
            "sector": row["sector"],
            "sector_warning": row["sector_warning"],
            "allocation": round(allocation, 2),
            "capped": allocation >= max_allowed - 0.01,
        })

        total_allocated += allocation

    remaining = round(adjusted_budget - total_allocated, 2)

    return allocations, adjusted_budget, remaining, regime_note


def run():

    print()
    print("=" * 70)
    print("SIP ALLOCATOR - PROFILE-BASED MONTHLY DEPLOYMENT")
    print("=" * 70)

    try:
        sip_budget = float(input("Monthly SIP budget (Rs): ").strip())
    except ValueError:
        print("[-] Invalid amount.")
        return

    if sip_budget <= 0:
        print("[-] Budget must be positive.")
        return

    candidates_df = load_compounder_candidates()

    if candidates_df.empty:
        print("[-] No real candidates found in compounder_candidates - "
              "run Compounder_Scanner.py first.")
        return

    regime = get_current_regime()

    allocations, adjusted_budget, remaining, regime_note = calculate_sip_allocation(
        candidates_df, sip_budget, regime, profile="Compounder"
    )

    print(f"\n[*] {regime_note}")
    print(f"[*] Effective budget this month: Rs{adjusted_budget:,.2f}")
    print()

    for a in allocations:
        cap_note = "  (capped at max position size)" if a["capped"] else ""
        has_warning = pd.notna(a["sector_warning"]) and a["sector_warning"]
        warn_note = f"  [!] {a['sector_warning']}" if has_warning else ""
        print(f"  {a['ticker']:<15} Rs{a['allocation']:>10,.2f}  "
              f"(score {a['score']:>6.2f}, {a['sector']}){cap_note}{warn_note}")

    print(f"\n[*] Total allocated: Rs{adjusted_budget - remaining:,.2f}")
    print(f"[*] Remaining, unallocated: Rs{remaining:,.2f}")

    if remaining > adjusted_budget * 0.3:
        print("[!] A large share of this month's budget is unallocated - "
              "few candidates cleared the quality gate, or the position cap "
              "is binding tightly. Consider whether that's genuinely correct "
              "before assuming the leftover should just carry forward.")

    result_df = pd.DataFrame(allocations)
    today = datetime.now().strftime("%Y-%m-%d")
    result_df["date"] = today
    result_df["sip_budget"] = sip_budget
    result_df["regime"] = regime

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sip_allocations (
            ticker TEXT,
            score REAL,
            sector TEXT,
            sector_warning TEXT,
            allocation REAL,
            capped INTEGER,
            date TEXT,
            sip_budget REAL,
            regime TEXT
        )
    """)
    conn.execute("DELETE FROM sip_allocations WHERE date = ?", (today,))
    result_df.to_sql("sip_allocations", conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, "SIP_ALLOCATION_PLAN.xlsx")
    save_excel_with_retry(result_df, excel_path, index=False)

    print(f"\n[+] Written to sip_allocations and {excel_path}")
    print("=" * 70)


if __name__ == "__main__":
    run()