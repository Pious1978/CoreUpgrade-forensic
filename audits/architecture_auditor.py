import os
import ast
import importlib.util
from typing import Dict, Any, List

class ArchitectureAuditor:
    def __init__(self, domains_root_dir: str):
        self.domains_root_dir = domains_root_dir

    def audit_boundaries(self) -> Dict[str, Any]:
        report = {"passed": True, "domains": {}}
        
        if not os.path.exists(self.domains_root_dir):
            return {"passed": False, "error": f"Directory not found: {self.domains_root_dir}"}

        domain_names = [
            d for d in os.listdir(self.domains_root_dir)
            if os.path.isdir(os.path.join(self.domains_root_dir, d))
        ]

        for domain in domain_names:
            domain_path = os.path.join(self.domains_root_dir, domain)
            manifest_path = os.path.join(domain_path, "manifest.py")
            
            checks = {"manifest": False, "forbidden_imports": True}
            domain_passed = True

            if os.path.exists(manifest_path):
                checks["manifest"] = True
                manifest_data = self._load_manifest(manifest_path)
                forbidden = manifest_data.get("FORBIDDEN_IMPORTS", [])
                
                # Run AST scan for forbidden imports
                if self._scan_forbidden_imports(domain_path, forbidden):
                    checks["forbidden_imports"] = False
                    domain_passed = False
            else:
                domain_passed = False

            report["domains"][domain] = {"status": "PASS" if domain_passed else "FAIL", "checks": checks}
            if not domain_passed:
                report["passed"] = False

        return report

    def _load_manifest(self, path: str) -> Dict[str, Any]:
        spec = importlib.util.spec_from_file_location("manifest", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return {k: getattr(mod, k) for k in dir(mod) if not k.startswith("_")}

    def _scan_forbidden_imports(self, domain_path: str, forbidden_domains: List[str]) -> bool:
        """Returns True if any forbidden import is discovered via AST analysis."""
        for root, _, files in os.walk(domain_path):
            for file in files:
                if file.endswith(".py"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.Import, ast.ImportFrom)):
                                    module_str = node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
                                    if module_str:
                                        for forbidden in forbidden_domains:
                                            if forbidden in module_str:
                                                return True
                        except SyntaxError:
                            continue
        return False
