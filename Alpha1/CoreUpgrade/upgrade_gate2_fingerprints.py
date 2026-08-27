import os
import ast
import hashlib
import json

print("--- UPGRADE GATE 2: ADDING CONTRACT FINGERPRINTING ---")

gate2_code = '''import os
import ast
import hashlib
import json
from typing import List, Dict

class ContractIntegrityGate:
    """
    Gate 2: Semantic Contract Integrity & Fingerprinting
    Enforces semantic purity and cryptographic API versioning via fingerprint hashes.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0
        self.fingerprint_path = os.path.join("event_store", "fingerprints", "contract_fingerprints.json")

    def run_all_checks(self):
        print("--- GATE 2: SEMANTIC CONTRACT INTEGRITY ---")
        
        self._check_semantic_purity("contracts")
        self._check_schema_immutability("research/contracts")
        self._check_domain_boundaries()
        self._check_contract_fingerprints()
        
        print(f"\\nGate 2 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Contract layer adheres to semantic purity and stable fingerprints.")
        else:
            print("Verdict: FAIL - Contract violations or breaking API changes detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_semantic_purity(self, directory: str):
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
                        violations.append(f"{file}: Syntax error: {e}")
                        continue

                has_classes = False
                for node in tree.body:
                    if isinstance(node, (ast.Expr, ast.Assign, ast.If, ast.For, ast.While, ast.Call)):
                        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            continue
                        violations.append(f"{file}: Contains unauthorized top-level executable code.")

                    if isinstance(node, ast.ClassDef):
                        has_classes = True
                        is_frozen = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call) and getattr(dec.func, 'id', '') == 'dataclass':
                                for kw in dec.keywords:
                                    if kw.arg == 'frozen' and getattr(kw.value, 'value', False) is True:
                                        is_frozen = True
                        if not is_frozen:
                            violations.append(f"{file}: Class '{node.name}' must be a @dataclass(frozen=True).")

                        if node.bases:
                            violations.append(f"{file}: Class '{node.name}' uses inheritance. Contracts must be flat.")

                        for body_item in node.body:
                            if isinstance(body_item, ast.FunctionDef):
                                violations.append(f"{file}: Class '{node.name}' contains method '{body_item.name}'.")

                if not has_classes:
                    violations.append(f"{file}: Module contains no class definitions.")

        self._assert(len(violations) == 0, 
                     f"Semantic Purity: All modules in {directory}/ contain exclusively pure schemas.", 
                     f"Violations:\\n" + "\\n".join(violations))

    def _check_schema_immutability(self, directory: str):
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
                        
        self._assert(len(invalid) == 0, f"Internal Immutability: {directory}/ schemas are frozen.", f"Mutable: {invalid}")

    def _check_domain_boundaries(self):
        violations = []
        violations.extend(self._scan_imports("contracts", forbidden=["research", "portfolio", "execution", "governance", "control_plane", "core"]))
        self._assert(len(violations) == 0, "Domain Boundaries: Contracts depend on zero runtime domain logic.", f"Violations:\\n" + "\\n".join(violations))

    def _check_contract_fingerprints(self):
        """Computes structural schema hashes and verifies them against the event store baseline."""
        current_fingerprints = {}
        contracts_dir = "contracts"
        
        if os.path.exists(contracts_dir):
            for file in sorted(os.listdir(contracts_dir)):
                if not file.endswith(".py") or file == "__init__.py": continue
                filepath = os.path.join(contracts_dir, file)
                
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Extract class name and fields with types
                        fields = []
                        for body_item in node.body:
                            if isinstance(body_item, ast.AnnAssign) and isinstance(body_item.target, ast.Name):
                                field_name = body_item.target.id
                                field_type = ast.unparse(body_item.annotation) if hasattr(ast, 'unparse') else str(body_item.annotation)
                                fields.append(f"{field_name}:{field_type}")
                        
                        schema_signature = f"{node.name}|" + "|".join(sorted(fields))
                        h = hashlib.sha256(schema_signature.encode()).hexdigest()[:12]
                        current_fingerprints[node.name] = h

        os.makedirs(os.path.dirname(self.fingerprint_path), exist_ok=True)
        
        # If baseline doesn't exist, initialize it automatically
        if not os.path.exists(self.fingerprint_path):
            with open(self.fingerprint_path, "w", encoding="utf-8") as f:
                json.dump(current_fingerprints, f, indent=4)
            print(f"[INFO] Initialized new contract fingerprint baseline at {self.fingerprint_path}")

        with open(self.fingerprint_path, "r", encoding="utf-8") as f:
            baseline_fingerprints = json.load(f)

        mismatches = []
        for name, current_hash in current_fingerprints.items():
            if name not in baseline_fingerprints:
                mismatches.append(f"New un-baselined contract detected: {name} ({current_hash})")
            elif baseline_fingerprints[name] != current_hash:
                mismatches.append(f"Breaking API Change! Contract '{name}' fingerprint changed ({baseline_fingerprints[name]} -> {current_hash}).")

        self._assert(len(mismatches) == 0, 
                     f"Contract Fingerprints Stable: All public schemas match baseline hashes.", 
                     f"Breaking changes detected:\\n" + "\\n".join(mismatches))

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

print("Gate 2 successfully upgraded to 4/4 checks with Contract Fingerprinting.")
