import os
import ast

print("--- REFACTORING CONTRACT LAYER ---")

# 1. Scaffold correct homes for runtime logic
os.makedirs("core", exist_ok=True)
os.makedirs("governance", exist_ok=True)

with open(os.path.join("core", "contract_runtime.py"), "w", encoding="utf-8") as f:
    f.write('''"""Core infrastructure for processing contracts. No business schemas here."""
class ContractBase: pass
class ContractValidationError(Exception): pass
''')
print("Created: core/contract_runtime.py")

with open(os.path.join("governance", "enums.py"), "w", encoding="utf-8") as f:
    f.write('''from enum import Enum
class GovernanceDecisionType(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
class GovernanceActionType(Enum):
    HALT = "halt"
    PROCEED = "proceed"
''')
print("Created: governance/enums.py")

# 2. Flag contaminated files in contracts/ instead of aggressively deleting
impure_keywords = ["ContractBase", "GovernanceActionType", "ContractValidationError", "GovernanceDecisionType"]
contracts_dir = "contracts"

if os.path.exists(contracts_dir):
    for filename in os.listdir(contracts_dir):
        if not filename.endswith(".py") or filename == "__init__.py": continue
        
        filepath = os.path.join(contracts_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        if any(kw in content for kw in impure_keywords):
            print(f"Requires manual review (infrastructure leakage detected): {filepath}")

# 3. Upgrade Gate 2 to enforce strict Contract Directory Purity
gate2_code = '''import os
import ast
from typing import List

class ContractIntegrityGate:
    """
    Gate 2: Contract Integrity
    Enforces strict Contract Directory Purity: 
    Only pure, flat, frozen dataclasses are allowed. No methods, no inheritance.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 2: CONTRACT INTEGRITY ---")
        
        self._check_directory_purity("contracts")
        self._check_schema_immutability("research/contracts")
        self._check_domain_boundaries()
        
        print(f"\\nGate 2 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Contract layer and domain firewalls are pure.")
        else:
            print("Verdict: FAIL - Boundary violations or mutable/logic-heavy contracts detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_directory_purity(self, directory: str):
        """Ensures public contracts are PURE schemas: no inheritance, no methods, only frozen dataclasses."""
        violations = []
        if not os.path.exists(directory): return

        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue
                
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read())
                    except SyntaxError:
                        continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # 1. Must be a frozen dataclass
                        is_frozen = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'dataclass':
                                for kw in dec.keywords:
                                    if kw.arg == 'frozen' and getattr(kw.value, 'value', False) is True:
                                        is_frozen = True
                        if not is_frozen:
                            violations.append(f"{file}: Class '{node.name}' must be a @dataclass(frozen=True).")

                        # 2. Must not inherit (flat schemas only)
                        if node.bases:
                            violations.append(f"{file}: Class '{node.name}' uses inheritance. Contracts must be flat.")

                        # 3. Must not contain business logic (methods)
                        for body_item in node.body:
                            if isinstance(body_item, ast.FunctionDef):
                                violations.append(f"{file}: Class '{node.name}' contains a method. Logic is strictly forbidden in schemas.")

        self._assert(len(violations) == 0, 
                     f"Contract Purity: {directory}/ contains only pure, flat, frozen schemas.", 
                     f"Purity violations found:\\n" + "\\n".join(violations))

    def _check_schema_immutability(self, directory: str):
        """Ensures internal contracts are at least frozen."""
        invalid = []
        if not os.path.exists(directory): return
        
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue
                with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        is_frozen = any(
                            isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'dataclass' 
                            and any(kw.arg == 'frozen' and getattr(kw.value, 'value', False) is True for kw in dec.keywords)
                            for dec in node.decorator_list
                        )
                        if not is_frozen: invalid.append(node.name)
                        
        self._assert(len(invalid) == 0, f"Internal Immutability: {directory}/ schemas are frozen.", f"Mutable classes: {invalid}")

    def _check_domain_boundaries(self):
        """Scans AST of domains to prevent illegal cross-domain internal imports."""
        violations = []
        
        violations.extend(self._scan_imports("portfolio", forbidden=["research.contracts", "research.internal"]))
        violations.extend(self._scan_imports("execution", forbidden=["research", "portfolio.construction", "portfolio.capacity"]))
        violations.extend(self._scan_imports("contracts", forbidden=["research", "portfolio", "execution", "governance"]))
        
        self._assert(len(violations) == 0, "Domain Boundaries: Strict separation enforced (No forbidden imports).", f"Boundary Violations:\\n" + "\\n".join(violations))

    def _scan_imports(self, directory: str, forbidden: List[str]) -> List[str]:
        violations = []
        if not os.path.exists(directory): return violations
        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py"): continue
                with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                    try: tree = ast.parse(f.read())
                    except SyntaxError: continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if any(alias.name.startswith(bad) for bad in forbidden):
                                violations.append(f"{file}: 'import {alias.name}'")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if any(node.module.startswith(bad) for bad in forbidden):
                            violations.append(f"{file}: 'from {node.module}'")
        return violations

if __name__ == "__main__":
    gate = ContractIntegrityGate()
    gate.run_all_checks()
'''

with open(os.path.join("audits", "gate2_contracts.py"), "w", encoding="utf-8") as f:
    f.write(gate2_code)

print("Upgraded audits/gate2_contracts.py to strict Contract Directory Purity.")
