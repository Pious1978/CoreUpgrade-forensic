"""
SIP_Allocator.py

Dual-sleeve, profile-based monthly SIP (systematic investment)
allocation - adapted from Alpha1's real long_planner.py
(MasterLongPlanner class) and long_planner_Highrisk.py's genuine
Core/High-Risk architecture, the most architecturally significant find
in the whole Obsolete-folder investigation.

Both sleeves now have real, independent candidate sources:
- Core sleeve: Compounder_Scanner.py's quality-gated, z-score-ranked
  output (stability, quality, moat-focused).
- High-Risk sleeve: HighRisk_Scanner.py's momentum-focused output
  (deliberately lenient quality bar, heavy weight on momentum/trend,
  drawdown penalized more severely).

Each sleeve gets its own budget, its own profile risk parameters
(Core: 15% max position / 20% stop; HighRisk: 3% max position / 5%
stop), and is allocated completely independently - matching Alpha1's
real Core-Satellite investment philosophy, not a single blended pool.

Depends on: the same Monday fundamentals coverage check as both
scanners - this is allocation logic sitting on top of their output, so
it's only as good as that output is.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

from core.config import DB_PATH, BASE_DIR
from core.excel_utils import save_excel_with_retry

PROFILES = {
    "Compounder": {"max_pos_size": 0.15, "stop_loss": 0.20},
    "HighRisk": {"max_pos_size": 0.03, "stop_loss": 0.05},
    # Growth is defined here for when its own scanner exists, but isn't
    # usable yet - no real candidate source feeds it today.
    "Growth": {"max_pos_size": 0.08, "stop_loss": 0.10},
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


def load_highrisk_candidates():
    """Real candidates from HighRisk_Scanner.py's own output - the
    momentum-focused sleeve, genuinely different criteria from the
    Compounder sleeve, not a hardcoded watchlist."""

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT ticker, score, sector, sector_warning
            FROM highrisk_candidates
            WHERE date = (SELECT MAX(date) FROM highrisk_candidates)
        """, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"[-] Could not load highrisk_candidates: {e}")
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


def process_sleeve(sleeve_name, profile, candidates_df, sip_budget, regime, table_name, excel_suffix):
    """
    Shared per-sleeve processing - runs allocation, prints the section,
    and writes results, for whichever sleeve (Core or High-Risk) is
    passed in. Keeps the two sleeves' handling identical in mechanics
    while their actual scoring/candidates stay genuinely independent.
    """

    print(f"\n{'-'*70}")
    print(f"{sleeve_name.upper()} SLEEVE")
    print(f"{'-'*70}")

    if candidates_df.empty:
        print(f"[-] No real candidates found - run the {sleeve_name} scanner first.")
        return None

    allocations, adjusted_budget, remaining, regime_note = calculate_sip_allocation(
        candidates_df, sip_budget, regime, profile=profile
    )

    print(f"[*] {regime_note}")
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
              "few candidates cleared the gate, or the position cap is "
              "binding tightly. Consider whether that's genuinely correct "
              "before assuming the leftover should just carry forward.")

    result_df = pd.DataFrame(allocations)
    today = datetime.now().strftime("%Y-%m-%d")
    result_df["date"] = today
    result_df["sip_budget"] = sip_budget
    result_df["regime"] = regime
    result_df["sleeve"] = sleeve_name

    conn = sqlite3.connect(DB_PATH)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            ticker TEXT,
            score REAL,
            sector TEXT,
            sector_warning TEXT,
            allocation REAL,
            capped INTEGER,
            date TEXT,
            sip_budget REAL,
            regime TEXT,
            sleeve TEXT
        )
    """)
    conn.execute(f"DELETE FROM {table_name} WHERE date = ?", (today,))
    result_df.to_sql(table_name, conn, if_exists="append", index=False)
    conn.close()

    excel_path = os.path.join(BASE_DIR, f"SIP_ALLOCATION_{excel_suffix}.xlsx")
    save_excel_with_retry(result_df, excel_path, index=False)

    print(f"[+] Written to {table_name} and {excel_path}")

    return result_df


def run():

    print()
    print("=" * 70)
    print("SIP ALLOCATOR - DUAL-SLEEVE MONTHLY DEPLOYMENT")
    print("=" * 70)
    print("Core-Satellite investing: a stable, quality-focused Core sleeve")
    print("and a smaller, momentum-focused High-Risk sleeve, allocated and")
    print("tracked completely independently.")

    try:
        core_budget = float(input("\nCore sleeve monthly budget (Rs): ").strip())
        highrisk_budget = float(input("High-Risk sleeve monthly budget (Rs): ").strip())
    except ValueError:
        print("[-] Invalid amount.")
        return

    if core_budget < 0 or highrisk_budget < 0:
        print("[-] Budgets must be non-negative.")
        return

    if core_budget == 0 and highrisk_budget == 0:
        print("[-] Both budgets are zero - nothing to allocate.")
        return

    regime = get_current_regime()

    if core_budget > 0:
        process_sleeve(
            "Core", "Compounder", load_compounder_candidates(),
            core_budget, regime, "sip_allocations_core", "CORE"
        )

    if highrisk_budget > 0:
        process_sleeve(
            "High-Risk", "HighRisk", load_highrisk_candidates(),
            highrisk_budget, regime, "sip_allocations_highrisk", "HIGHRISK"
        )

    print(f"\n{'='*70}")
    print(f"Total monthly deployment: Rs{core_budget + highrisk_budget:,.2f}  "
          f"(Core Rs{core_budget:,.2f} + High-Risk Rs{highrisk_budget:,.2f})")
    print("=" * 70)


if __name__ == "__main__":
    run()