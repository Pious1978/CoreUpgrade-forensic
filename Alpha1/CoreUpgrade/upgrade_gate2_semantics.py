import os

gate2_semantic_code = '''import os
import ast
from typing import List

class ContractIntegrityGate:
    """
    Gate 2: Contract Integrity (Semantic Enforcement Engine)
    Evaluates contracts based on semantic properties (frozen dataclasses, 
    flat structure, zero execution logic) rather than rigid filename allowlists.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 2: SEMANTIC CONTRACT INTEGRITY ---")
        
        self._check_semantic_purity("contracts")
        self._check_schema_immutability("research/contracts")
        self._check_domain_boundaries()
        
        print(f"\\nGate 2 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Contract layer adheres strictly to semantic purity rules.")
        else:
            print("Verdict: FAIL - Semantic violations or logic-heavy contracts detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_semantic_purity(self, directory: str):
        """
        Enforces Semantic Rules 1-4:
        - Every public module must contain only frozen dataclasses.
        - Forbidden: methods, inheritance, exceptions, runtime classes, business logic, executable code.
        """
        violations = []
        if not os.path.exists(directory): return

        for root, _, files in os.walk(directory):
            for file in files:
                if not file.endswith(".py") or file == "__init__.py": continue
                
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    try:
                        tree = ast.parse(f.read())
                    except SyntaxError as e:
                        violations.append(f"{file}: Syntax error in contract file: {e}")
                        continue

                has_classes = False
                for node in tree.body:
                    # Rule 4: Check for top-level executable code outside of imports/dataclasses
                    if isinstance(node, (ast.Expr, ast.Assign, ast.If, ast.For, ast.While, ast.Call)):
                        # Allow module-level docstrings or simple constants
                        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            continue # Docstring allowed
                        violations.append(f"{file}: Contains unauthorized top-level executable code or statements.")

                    if isinstance(node, ast.ClassDef):
                        has_classes = True
                        
                        # Rule 1 & 3: Must be a frozen dataclass
                        is_frozen = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'dataclass':
                                for kw in dec.keywords:
                                    if kw.arg == 'frozen' and getattr(kw.value, 'value', False) is True:
                                        is_frozen = True
                        if not is_frozen:
                            violations.append(f"{file}: Class '{node.name}' must be a @dataclass(frozen=True).")

                        # Rule 2: Must not inherit (flat schemas only)
                        if node.bases:
                            violations.append(f"{file}: Class '{node.name}' uses inheritance. Contracts must be flat.")

                        # Rule 2: Must not contain methods or business logic
                        for body_item in node.body:
                            if isinstance(body_item, ast.FunctionDef):
                                violations.append(f"{file}: Class '{node.name}' contains method '{body_item.name}'. Logic is strictly forbidden in schemas.")

                if not has_classes:
                    violations.append(f"{file}: Module contains no class definitions.")

        self._assert(len(violations) == 0, 
                     f"Semantic Purity: All modules in {directory}/ contain exclusively pure, flat, frozen schemas.", 
                     f"Semantic violations found:\\n" + "\\n".join(violations))

    def _check_schema_immutability(self, directory: str):
        """Ensures internal research contracts are frozen dataclasses."""
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
        """Rule 5: Scans AST of contracts to ensure they do not import forbidden runtime domains."""
        violations = []
        # Contracts must never depend on implementation domains
        violations.extend(self._scan_imports("contracts", forbidden=["research", "portfolio", "execution", "governance", "control_plane", "core"]))
        
        self._assert(len(violations) == 0, "Domain Boundaries: Contracts depend on zero runtime domain logic.", f"Boundary Violations:\\n" + "\\n".join(violations))

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
    f.write(gate2_semantic_code)

print("Upgraded audits/gate2_contracts.py to Semantic Enforcement Rules.")
