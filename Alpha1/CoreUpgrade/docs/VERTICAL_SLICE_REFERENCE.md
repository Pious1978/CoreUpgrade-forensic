# Vertical Slice Complete (VSC) Reference Architecture (V1.0)

## Purpose
The VSC is not intended to be production code. 

Its purpose is to provide a deterministic executable specification of the platform's business lifecycle. Production implementations may replace any stage implementation provided they preserve the architectural invariants defined in `vsc/invariants.py`.

---

## Stable Guarantees

The following are considered absolute architectural contracts. Any alterations require an explicit architecture review:

* **Pipeline Version:** Locked to `1.0`.
* **Seven-Stage Pipeline:** The complete lifecycle strictly flows through Research, Governance, Portfolio Intent, Portfolio Decision, Execution Plan, Execution Result, and Performance Feedback.
* **Immutable Contracts:** Enforced via frozen data classes (`frozen=True`); modification attempts raise `FrozenInstanceError`.
* **Root Lineage Preservation:** Every contract across the chain preserves the originating `root_contract_id`.
* **Parent Lineage Preservation & Graph Integrity:** Immediate predecessor references maintain acyclic lineage via `parent_contract_id` with strictly unique IDs.
* **Correlation Preservation:** End-to-end telemetry and analytical queries link via `correlation_id`.
* **Trust State Transitions:** Predictable state progression from `RAW` → `GOVERNANCE_CERTIFIED` → `ANALYTICAL`.
* **Deterministic Execution:** Zero manual intervention, non-decreasing timestamps, and guaranteed reproducible test outputs.
* **End-to-End VSC Regression Harness:** The integration test suite (`vsc/test_vsc.py`) must pass cleanly on every build.

---

## Governance Rule
> **No modification to `vsc/invariants.py` without an Architecture Decision Record (ADR).** 
> 
> This file holds the public architectural API status of the platform.

---

## Future Roadmap Phases
Future development must extend behind these stable contracts without altering the core pipeline:
* **Phase 2:** Replace mock research generator with real quantitative scanner.
* **Phase 3:** Replace deterministic allocation with institutional portfolio optimizers.
* **Phase 4:** Replace paper broker simulator with live broker adapters (e.g., Interactive Brokers, Alpaca).
* **Phase 5:** Replace static feedback with dynamic machine learning attribution engines.