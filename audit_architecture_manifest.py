import os

REQUIRED_PATHS = [
    "research",
    "research/feedback",
    "research/contracts",

    "portfolio",
    "portfolio/capacity",
    "portfolio/risk_budget",
    "portfolio/rebalance",

    "governance",
    "governance/audit_controls",

    "control_plane",
    "control_plane/workflow_scheduler.py",

    "event_store",
    "event_store/snapshots",
    "event_store/fingerprints",

    "contracts",
    "audits"
]


FORBIDDEN_PATHS = [
    "engine/audit_suite.py",
    "control_plane/execution_scheduler.py",
]


def check_paths():

    passed = True

    print("--- ARCHITECTURE MANIFEST AUDIT ---")

    for path in REQUIRED_PATHS:
        if os.path.exists(path):
            print(f"[PASS] {path}")
        else:
            print(f"[FAIL] Missing: {path}")
            passed = False


    for path in FORBIDDEN_PATHS:
        if os.path.exists(path):
            print(f"[FAIL] Forbidden: {path}")
            passed = False
        else:
            print(f"[PASS] Removed: {path}")


    print()

    if passed:
        print("Architecture Manifest Result: PASS")
    else:
        print("Architecture Manifest Result: FAIL")

    return passed


if __name__ == "__main__":
    check_paths()
