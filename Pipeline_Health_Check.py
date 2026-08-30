"""
Pipeline_Health_Check.py

Connects the four confirmed-real, read-only audit tools found tonight
(DB_Audit.py, Trade_Candidate_Audit.py, Trigger_Input_Audit.py,
Risk_Input_Audit.py) into one routine, meant to be run periodically
(e.g., once a week, or after any real pipeline change) as a genuine
sanity check on the state of the database - not part of the automated
nightly pipeline, purely diagnostic.

Risk_Input_Audit.py was refactored to wrap its logic in a proper run()
function rather than executing immediately at import time (the other
three already had this structure) - same behavior, just safely
callable and consistent with the others.

Each audit runs independently, wrapped in its own try/except - a
missing or empty table in one section (e.g., a fresh database with no
candidates yet) is reported clearly rather than crashing the whole
routine and losing the other three audits' results.
"""

import DB_Audit
import Trade_Candidate_Audit
import Trigger_Input_Audit
import Risk_Input_Audit


AUDITS = [
    ("Database Table Inventory & Research Watchlist Health", DB_Audit.run),
    ("Trade Candidate Quality", Trade_Candidate_Audit.audit),
    ("Trigger Input Quality", Trigger_Input_Audit.run_trigger_input_audit),
    ("Risk Engine Input Quality", Risk_Input_Audit.run),
]


def run():

    print()
    print("#" * 70)
    print("PIPELINE HEALTH CHECK")
    print("#" * 70)
    print("Read-only, diagnostic only - checks the real state of your")
    print("database against what each stage of the pipeline actually needs.")
    print("Not part of the automated nightly pipeline.")

    results = []

    for name, audit_fn in AUDITS:

        print(f"\n\n{'='*70}")
        print(f"RUNNING: {name}")
        print("=" * 70)

        try:
            audit_fn()
            results.append((name, "OK"))

        except Exception as e:
            print(f"[!] This audit failed to complete: {e}")
            results.append((name, f"FAILED - {e}"))

    print(f"\n\n{'#'*70}")
    print("HEALTH CHECK SUMMARY")
    print("#" * 70)

    for name, status in results:
        marker = "[+]" if status == "OK" else "[!]"
        print(f"{marker} {name}: {status}")

    failed = [r for r in results if r[1] != "OK"]

    if failed:
        print(f"\n[!] {len(failed)} of {len(results)} audits reported a problem - review above.")
    else:
        print(f"\n[+] All {len(results)} audits completed cleanly.")

    print("#" * 70)


if __name__ == "__main__":
    run()