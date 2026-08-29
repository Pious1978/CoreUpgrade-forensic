import os
import shutil

CONFIRMED_DEAD = [
    "Breakout_Trigger_Scanner.py",
    "Execution_Ranking_Engine.py",
    "Execution_State_Machine.py",
    "Live_Execution_Monitor_new.py",
    "check_all_stale.py",
    "check_bharti.py",
    "check_composite.py",
    "check_compression_variance.py",
    "check_concentration.py",
    "check_consensus_pivots.py",
    "check_daily_snapshot_factors.py",
    "check_daily_snapshot_factors2.py",
    "check_exact_overlap.py",
    "check_factor_availability.py",
    "check_movers.py",
    "check_overlap.py",
    "check_precise.py",
    "check_remaining_factors.py",
    "check_rs_availability_in_tier1.py",
    "check_schema.py",
    "check_shares.py",
    "check_specific_tiers.py",
    "check_tables.py",
    "check_tier_distribution.py",
    "check_watchlist_dates.py",
    "check_yahoo_schema.py",
    "cleanup_stale_data.py",
    "diagnose_rvol.py",
    "diagnose_rvol2.py",
    "diagnose_concurrent.py",
    "spot_check_smallcaps.py",
    "verify_backfill_integrity.py",
    "monitor_output.txt",
    "runner_output.txt",
]

os.makedirs("Scrap", exist_ok=True)

moved = []
missing = []

for f in CONFIRMED_DEAD:
    if os.path.exists(f):
        shutil.move(f, os.path.join("Scrap", f))
        moved.append(f)
    else:
        missing.append(f)

print(f"Moved {len(moved)} files to Scrap/")
if missing:
    print(f"Not found (already gone or renamed): {missing}")
