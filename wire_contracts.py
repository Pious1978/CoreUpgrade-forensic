import os
import re

def update_file(filepath, imports_to_add, replacements):
    if not os.path.exists(filepath):
        print(f"Skipping {filepath} - file not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Add imports if not present
    for imp in imports_to_add:
        if imp not in content:
            # Insert right after the first import or at the top
            content = imp + "\n" + content

    # Apply signature replacements
    for old, new in replacements:
        content = content.replace(old, new)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Successfully wired contracts into {filepath}")

# 1. Wire Risk and Validation into the Optimizer
optimizer_file = os.path.join("portfolio", "optimizer.py")
optimizer_imports = [
    "from typing import List, Dict",
    "from contracts.risk_constraints import RiskConstraints",
    "from contracts.signal_validation import SignalValidationResult"
]
optimizer_replacements = [
    (
        "def optimize_max_sharpe(self, risk_free_rate: float = 0.06, max_weight: float = 0.25) -> Dict[str, float]:",
        "def optimize_max_sharpe(\n        self,\n        validated_signals: List[SignalValidationResult],\n        risk_constraints: RiskConstraints,\n        risk_free_rate: float = 0.06\n    ) -> Dict[str, float]:\n        # Filter out failed signals before optimization\n        eligible_signals = [s for s in validated_signals if s.verdict != 'FAIL']\n"
    )
]

# 2. Wire Execution Feedback into the Capacity/Slippage Model
slippage_file = os.path.join("portfolio", "capacity", "slippage_model.py")
slippage_imports = [
    "from typing import List",
    "from contracts.execution_report import ExecutionReport"
]
slippage_replacements = [
    (
        "class SlippageModel:",
        "class SlippageModel:\n    def update_from_execution_reports(self, reports: List[ExecutionReport]) -> None:\n        \"\"\"Feedback loop: adjust capacity model based on actual slippage\"\"\"\n        pass\n"
    )
]

# 3. Wire the Orchestrator to consume these contracts
orchestrator_file = os.path.join("portfolio", "rebalancing", "rebalance_orchestrator.py")
orchestrator_imports = [
    "from typing import List",
    "from contracts.risk_constraints import RiskConstraints",
    "from contracts.signal_validation import SignalValidationResult"
]
orchestrator_replacements = [
    (
        "def execute_rebalance_cycle(self, target_weights: Dict[str, float], market_data_map: Dict[str, Dict[str, float]]) -> Dict[str, Any]:",
        "def execute_rebalance_cycle(\n        self,\n        validated_signals: List[SignalValidationResult],\n        risk_constraints: RiskConstraints,\n        market_data_map: Dict[str, Dict[str, float]]\n    ) -> Dict[str, Any]:"
    )
]

# Execute wiring
update_file(optimizer_file, optimizer_imports, optimizer_replacements)
update_file(slippage_file, slippage_imports, slippage_replacements)
update_file(orchestrator_file, orchestrator_imports, orchestrator_replacements)
