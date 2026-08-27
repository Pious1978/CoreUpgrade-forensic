# VSC Evolution Policy

## Core Directives
1. **Contracts are Immutable:** Once defined in `contracts/`, domain contracts (`BaseContract` subclasses) are immutable (`frozen=True`) and must never be altered or retrofitted with business logic.
2. **Semantic Stability:** Existing stages (`Governance`, `Portfolio`, `Execution`, `Feedback`) cannot change their input/output semantics without a formal architecture review.
3. **Interface Compliance:** New implementations must satisfy existing stage protocols (`Stage[InT, OutT]`).
4. **Baseline Invariance:** The VSC 1.1 baseline test suite (`python -m vsc.test_vsc`) must always pass cleanly on every build.
5. **Horizontal Extension:** New capabilities enter the platform exclusively through component replacement (e.g., swapping a mock generator for a real scanner), leaving orchestrators and downstream pipelines untouched.