import os

# --- 1. INTERNAL RESEARCH CONTRACTS ---
internal_contracts = {
    "feature_set.py": '''from dataclasses import dataclass, field
from typing import Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class FeatureSet:
    snapshot_hash: str
    features: Dict[str, float]
    computation_timestamp: datetime
''',
    "alpha_model_output.py": '''from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class AlphaModelOutput:
    model_id: str
    raw_score: float
    confidence_interval: float
    regime_state: str
    computation_timestamp: datetime
''',
    "backtest_result.py": '''from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class BacktestResult:
    signal_id: str
    oos_sharpe: float
    walk_forward_pass_rate: float
    capacity_limit_usd: float
    metrics: Dict[str, float]
'''
}

os.makedirs(os.path.join("research", "contracts"), exist_ok=True)
for filename, content in internal_contracts.items():
    with open(os.path.join("research", "contracts", filename), "w", encoding="utf-8") as f:
        f.write(content)

# --- 2. CROSS-DOMAIN PUBLIC CONTRACTS ---
public_contracts = {
    "research_signal.py": '''from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ResearchSignalContract:
    """Public boundary contract between Research and Portfolio."""
    symbol: str
    direction: int  # 1 (Long), -1 (Short)
    strength_score: float
    artifact_hash: str
    generated_at: datetime
''',
    "risk_limits.py": '''from dataclasses import dataclass

@dataclass(frozen=True)
class RiskLimitContract:
    """Public boundary contract between Risk/Governance and Portfolio."""
    max_position_size: float
    max_sector_exposure: float
    max_drawdown_limit: float
''',
    "portfolio_intent.py": '''from dataclasses import dataclass
from typing import Dict
from datetime import datetime

@dataclass(frozen=True)
class PortfolioIntentContract:
    """Public boundary contract between Portfolio and Execution."""
    target_weights: Dict[str, float]
    rebalance_timestamp: datetime
    execution_urgency: str
''',
    "execution_plan.py": '''from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ExecutionPlanContract:
    """Public boundary routing contract."""
    symbol: str
    target_shares: int
    algo_strategy: str
    price_limit: float
    timestamp: datetime
'''
}

os.makedirs("contracts", exist_ok=True)
for filename, content in public_contracts.items():
    with open(os.path.join("contracts", filename), "w", encoding="utf-8") as f:
        f.write(content)

# --- 3. GATE 2: CONTRACT INTEGRITY AUDIT ---
gate2_code = '''import os
import ast
from typing import List

class ContractIntegrityGate:
    """
    Gate 2: Contract Integrity
    Verifies that all contracts are immutable (@dataclass(frozen=True))
    and that domains strictly obey public vs. internal import boundaries.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 2: CONTRACT INTEGRITY ---")
        
        self._check_schema_immutability("contracts")
        self._check_schema_immutability("research/contracts")
        
        # Hard boundary enforcement via AST
        self._check_domain_boundaries()
        
        print(f"\\nGate 2 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Contract layer and domain firewalls are secure.")
        else:
            print("Verdict: FAIL - Boundary violations or mutable contracts detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_schema_immutability(self, directory: str):
        """Ensures every class in the contract directories is a frozen dataclass."""
        invalid_classes = []
        
        if not os.path.exists(directory):
            return
            
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue
                
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        is_frozen = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'dataclass':
                                for kw in dec.keywords:
                                    if kw.arg == 'frozen' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                        is_frozen = True
                        if not is_frozen:
                            invalid_classes.append(node.name)
                            
        self._assert(len(invalid_classes) == 0, 
                     f"Immutability: All classes in {directory}/ are frozen dataclasses.", 
                     f"Mutable classes found in {directory}/: {invalid_classes}")

    def _check_domain_boundaries(self):
        """Scans AST of domains to prevent illegal cross-domain internal imports."""
        violations = []
        
        # Rule 1: Portfolio cannot import Research internals.
        violations.extend(self._scan_imports("portfolio", forbidden=["research.contracts", "research.internal"]))
        # Rule 2: Execution cannot import Research or Portfolio internals.
        violations.extend(self._scan_imports("execution", forbidden=["research", "portfolio.construction", "portfolio.capacity"]))
        # Rule 3: Root Contracts cannot depend on internal domain logic.
        violations.extend(self._scan_imports("contracts", forbidden=["research", "portfolio", "execution", "governance"]))
        
        self._assert(len(violations) == 0, 
                     "Domain Boundaries: Strict separation enforced (No forbidden imports).", 
                     f"Boundary Violations Detected:\\n" + "\\n".join(violations))

    def _scan_imports(self, directory: str, forbidden: List[str]) -> List[str]:
        violations = []
        if not os.path.exists(directory):
            return violations
            
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py"): continue
                
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read())
                    except SyntaxError:
                        continue
                        
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            for bad in forbidden:
                                if alias.name.startswith(bad):
                                    violations.append(f"{filepath}: 'import {alias.name}'")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for bad in forbidden:
                                if node.module.startswith(bad):
                                    violations.append(f"{filepath}: 'from {node.module} import ...'")
        return violations

if __name__ == "__main__":
    gate = ContractIntegrityGate()
    gate.run_all_checks()
'''

with open(os.path.join("audits", "gate2_contracts.py"), "w", encoding="utf-8") as f:
    f.write(gate2_code)

print("Created Contracts and audits/gate2_contracts.py")
