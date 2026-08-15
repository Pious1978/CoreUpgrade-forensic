import os

# 1. Freeze Architecture Rules Manifest
manifest_content = """# Institutional Architecture Rules Manifest

## 1. Contract Boundaries
*   **Internal Contracts:** Reside inside domains (e.g., `research/contracts/`). Used exclusively for intra-domain communication.
*   **Cross-Domain Contracts:** Reside at the root `contracts/`. Used exclusively for inter-domain communication.
*   *Rule:* A domain may never import another domain's internal contract.

## 2. Validation vs. Certification
*   **Science (Research):** The `research/validation` domain owns the calculation of statistics, walk-forward analysis, and bias testing. It outputs artifact JSONs.
*   **Certification (Audits):** `audits/gate7_research_validity.py` does NOT calculate metrics. It consumes research artifacts and certifies them against institutional thresholds.

## 3. Policy vs. Execution
*   **Policy (Governance):** `governance/audit_controls/` defines *what* must be checked (YAML rules, thresholds).
*   **Execution (Audits):** `audits/` executes the checks defined by governance.

## 4. The Feedback Loop
*   Execution reality MUST feed back into Research and Portfolio models.
*   Flow: Execution -> Event Store -> `research/feedback` -> Model Retraining.
*   Flow: Execution -> Event Store -> `portfolio/capacity` -> Dynamic Position Sizing.

## 5. Gate Nomenclature
Gates 1-7 are Platform & Integrity Gates. They evaluate the system and the data.
*   Gate 1: Architecture Integrity
*   Gate 2: Contract Integrity
*   Gate 3: Dependency Integrity
*   Gate 4: Runtime Integrity
*   Gate 5: Data Lineage Integrity
*   Gate 6: Reproducibility Integrity
*   Gate 7: Research Alpha Validity (Artifact Certification)
"""

with open("ARCHITECTURE_RULES.md", "w", encoding="utf-8") as f:
    f.write(manifest_content)

print("Created ARCHITECTURE_RULES.md")

# 2. Scaffold Missing Domains & Clean Up Naming
directories_to_create = [
    os.path.join("research", "feedback"),
    os.path.join("research", "contracts"),
    os.path.join("portfolio", "capacity"),
    os.path.join("portfolio", "rebalance"),
    os.path.join("portfolio", "risk_budget"),
    os.path.join("governance", "audit_controls"),
    os.path.join("event_store", "snapshots", "market"),
    os.path.join("event_store", "snapshots", "features"),
    os.path.join("event_store", "snapshots", "portfolio"),
    os.path.join("event_store", "snapshots", "execution"),
    os.path.join("event_store", "fingerprints")
]

for directory in directories_to_create:
    os.makedirs(directory, exist_ok=True)
    init_file = os.path.join(directory, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            pass
    print(f"Verified/Created: {directory}")

# 3. Rename Execution Scheduler to Workflow Scheduler
control_plane_dir = "control_plane"
old_scheduler = os.path.join(control_plane_dir, "execution_scheduler.py")
new_scheduler = os.path.join(control_plane_dir, "workflow_scheduler.py")

if os.path.exists(old_scheduler):
    os.rename(old_scheduler, new_scheduler)
    print(f"Renamed: {old_scheduler} -> {new_scheduler}")
elif not os.path.exists(new_scheduler):
    with open(new_scheduler, "w", encoding="utf-8") as f:
        f.write("# Workflow Scheduler\\n")
    print(f"Created: {new_scheduler}")
