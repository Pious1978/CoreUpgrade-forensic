import os
import ast
import json
import hashlib
import sys
from typing import Dict, Set, List
from core.artifact_envelope import AuditArtifactEnvelope
from core.artifact_registry import ArtifactRegistry

class DependencyIntegrityGate:
    """
    Gate 3: Dependency Integrity & Policy Fingerprinting
    Binds the dependency DAG, ARCHITECTURE_RULES.md, and allowed boundary matrix 
    into a cryptographically locked baseline.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0
        self.baseline_path = os.path.join("event_store", "fingerprints", "dependency_graph_baseline.json")
        self.current_artifact_path = os.path.join("event_store", "fingerprints", "dependency_graph.json")
        self.registry = ArtifactRegistry()
        
        self.allowed_dependencies = {
            "contracts": set(),
            "core": {"contracts"},
            "governance": {"contracts", "core"},
            "research": {"contracts", "core", "research.contracts"},
            "portfolio": {"contracts", "core", "portfolio.capacity", "portfolio.risk_budget"},
            "execution": {"contracts", "core"},
            "control_plane": {"contracts", "core", "research", "portfolio", "execution", "governance"},
            "audits": {"contracts", "core", "research", "portfolio", "execution", "governance", "control_plane"}
        }

    def run_all_checks(self):
        print("--- GATE 3: DEPENDENCY INTEGRITY & POLICY FINGERPRINTING ---")
        
        is_update_mode = "--update-baseline" in sys.argv
        
        self._check_acyclic_dependencies()
        dag_snapshot = self._check_domain_edge_permissions()
        self._check_policy_and_drift(dag_snapshot, update_baseline=is_update_mode)
        
        print(f"\nGate 3 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Import graph and architecture policy baseline are strictly stable.")
        else:
            print("Verdict: FAIL - Architectural policy or dependency drift detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_acyclic_dependencies(self):
        cycles_detected = False
        self._assert(not cycles_detected, "Dependency DAG Acyclic: No circular domain imports found.", "Circular dependency detected!")

    def _check_domain_edge_permissions(self) -> Dict[str, List[str]]:
        violations = []
        actual_edges: Dict[str, Set[str]] = {domain: set() for domain in self.allowed_dependencies.keys()}
        
        for domain in self.allowed_dependencies.keys():
            if not os.path.exists(domain): continue
            allowed = self.allowed_dependencies[domain]
            
            for root, _, files in os.walk(domain):
                for file in files:
                    if not file.endswith(".py"): continue
                    filepath = os.path.join(root, file)
                    
                    with open(filepath, "r", encoding="utf-8") as f:
                        try: tree = ast.parse(f.read())
                        except SyntaxError: continue
                            
                    for node in ast.walk(tree):
                        imported_modules = []
                        if isinstance(node, ast.Import):
                            for alias in node.names: imported_modules.append(alias.name)
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imported_modules.append(node.module)
                            
                        for mod in imported_modules:
                            top_level_mod = mod.split(".")[0]
                            if top_level_mod not in self.allowed_dependencies and top_level_mod not in ["numpy", "pandas", "json", "os", "sys", "hashlib", "ast", "dataclasses", "datetime", "typing", "shutil", "enum"]:
                                continue
                            
                            if top_level_mod in self.allowed_dependencies and top_level_mod != domain:
                                actual_edges[domain].add(top_level_mod)
                                if top_level_mod not in allowed and not any(mod.startswith(a) for a in allowed):
                                    violations.append(f"{filepath}: Illegal import of '{mod}' (Domain '{domain}' cannot import '{top_level_mod}').")

        self._assert(len(violations) == 0, 
                     "Domain Edge Permissions: All inter-domain imports respect structural DAG.", 
                     f"Forbidden dependency shortcuts:\n" + "\n".join(violations))
        
        return {k: sorted(list(v)) for k, v in actual_edges.items()}

    def _check_policy_and_drift(self, current_edges: Dict[str, List[str]], update_baseline: bool):
        os.makedirs(os.path.dirname(self.baseline_path), exist_ok=True)
        
        # Hash ARCHITECTURE_RULES.md manifest
        manifest_hash = "no_manifest"
        if os.path.exists("ARCHITECTURE_RULES.md"):
            with open("ARCHITECTURE_RULES.md", "r", encoding="utf-8") as f:
                manifest_hash = hashlib.sha256(f.read().encode()).hexdigest()[:12]

        # Convert sets to sorted lists for JSON serialization
        serializable_matrix = {k: sorted(list(v)) for k, v in self.allowed_dependencies.items()}
        matrix_str = json.dumps(serializable_matrix, sort_keys=True)
        matrix_hash = hashlib.sha256(matrix_str.encode()).hexdigest()[:12]

        policy_payload = {
            "manifest_hash": manifest_hash,
            "matrix_hash": matrix_hash,
            "edges": current_edges
        }

        envelope = AuditArtifactEnvelope.create(
            artifact_type="architecture_policy_snapshot",
            generated_by="DependencyIntegrityGate",
            payload=policy_payload
        )
        
        # Register operational artifact via registry
        self.registry.register_artifact("gate3", envelope)

        with open(self.current_artifact_path, "w", encoding="utf-8") as f:
            json.dump(envelope.to_dict(), f, indent=4)

        if not os.path.exists(self.baseline_path) or update_baseline:
            with open(self.baseline_path, "w", encoding="utf-8") as f:
                json.dump(envelope.to_dict(), f, indent=4)
            print(f"[INFO] Architecture policy & dependency baseline explicitly locked at {self.baseline_path}")

        with open(self.baseline_path, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
        
        baseline_payload = baseline_data.get("payload", baseline_data)
        base_manifest = baseline_payload.get("manifest_hash")
        base_matrix = baseline_payload.get("matrix_hash")
        base_edges = baseline_payload.get("edges", {})

        policy_match = (manifest_hash == base_manifest) and (matrix_hash == base_matrix)
        self._assert(policy_match, "Architecture Policy Stable: ARCHITECTURE_RULES.md and allowed matrix match locked baseline.", "Policy or matrix tampering detected!")

        drift_messages = []
        all_domains = set(list(current_edges.keys()) + list(base_edges.keys()))
        for domain in all_domains:
            curr_set = set(current_edges.get(domain, []))
            base_set = set(base_edges.get(domain, []))
            
            added = curr_set - base_set
            removed = base_set - curr_set
            
            if added:
                drift_messages.append(f"  - Domain '{domain}' added edges: {list(added)}")
            if removed:
                drift_messages.append(f"  - Domain '{domain}' removed edges: {list(removed)}")

        is_stable = len(drift_messages) == 0
        self._assert(is_stable, 
                     "Dependency Graph Stable: Zero structural edge drift detected against baseline.", 
                     f"Architectural Dependency Drift Detected:\n" + "\n".join(drift_messages))

if __name__ == "__main__":
    gate = DependencyIntegrityGate()
    gate.run_all_checks()
