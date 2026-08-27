# Institutional Architecture Rules Manifest

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
