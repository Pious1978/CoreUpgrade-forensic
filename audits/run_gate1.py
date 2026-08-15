import os
import ast
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

EXPLICIT_DOMAINS = {
    "research",
    "portfolio",
    "risk",
    "governance",
    "execution",
    "control_plane",
    "contracts",
    "infrastructure",
    "event_store",
    "replay",
    "audits"
}

class InstitutionalStaticArchitectureVerifier:
    """
    Institutional Gate 1 Static Architecture Verification Engine.
    Performs deep AST inspection of real project code (classes, methods, fully-qualified paths),
    enforces manifest rules, detects fully-qualified API collisions, and checks dependency graphs.
    """
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()

    def verify_all(self) -> Dict[str, Any]:
        report = {
            "gate": "Gate 1 - Institutional Static Architecture Verification",
            "passed": True,
            "domains": {},
            "global_checks": {
                "no_cyclic_dependencies": True,
                "forbidden_imports_clean": True,
                "fully_qualified_apis_unique": True
            },
            "violations": []
        }

        domain_reports = {}
        dependency_graph: Dict[str, Set[str]] = {d: set() for d in EXPLICIT_DOMAINS}
        global_fq_api_registry: Dict[str, str] = {}  # fully_qualified_path -> domain_name
        all_violations = []

        for domain in EXPLICIT_DOMAINS:
            domain_path = self.project_root / domain
            domain_result, passed, imports, domain_fq_symbols = self._verify_domain_deep(domain, domain_path)
            domain_reports[domain] = domain_result
            
            if not passed:
                report["passed"] = False

            # Check fully-qualified API uniqueness across the project
            public_api = domain_result.get("public_api", {})
            # Support both dict mapping {'alias': 'path'} and list of strings
            api_paths = public_api.values() if isinstance(public_api, dict) else public_api
            
            for path in api_paths:
                fq_key = f"{domain}.{path}"
                if fq_key in global_fq_api_registry:
                    existing_domain = global_fq_api_registry[fq_key]
                    all_violations.append(f"Duplicate fully-qualified API path '{fq_key}' in domain '{domain}' (already bound in '{existing_domain}')")
                    report["passed"] = False
                    report["global_checks"]["fully_qualified_apis_unique"] = False
                else:
                    global_fq_api_registry[fq_key] = domain

            # Build dependency edges
            for imported_mod in imports:
                if imported_mod in EXPLICIT_DOMAINS and imported_mod != domain:
                    dependency_graph[domain].add(imported_mod)

            # Verify forbidden imports declared in manifest
            forbidden = domain_result.get("forbidden_imports_list", [])
            for imported_mod in imports:
                if imported_mod in forbidden:
                    all_violations.append(f"Domain '{domain}' illegally imports forbidden domain '{imported_mod}'")
                    report["passed"] = False
                    report["global_checks"]["forbidden_imports_clean"] = False

        # Check for cyclic dependencies using DFS
        has_cycle, cycle_path = self._detect_cycles(dependency_graph)
        if has_cycle:
            report["passed"] = False
            report["global_checks"]["no_cyclic_dependencies"] = False
            report["global_checks"]["cycle_path"] = cycle_path
            all_violations.append(f"Cyclic dependency detected: {' -> '.join(cycle_path)}")

        report["domains"] = domain_reports
        report["violations"] = all_violations
        return report

    def _verify_domain_deep(self, domain_name: str, domain_path: Path) -> Tuple[Dict[str, Any], bool, Set[str], Set[str]]:
        checks = {
            "directory_exists": False,
            "manifest_exists": False,
            "init_exists": False,
            "domain_name_matches": False,
            "version_declared": False,
            "public_api_defined": False,
            "public_api_symbols_resolve": True,
            "forbidden_imports_clean": True
        }
        domain_passed = True
        imported_modules: Set[str] = set()
        fully_qualified_symbols: Set[str] = set()
        public_api: Any = {}
        forbidden_imports: List[str] = []

        if not domain_path.exists() or not domain_path.is_dir():
            return {"status": "FAIL", "checks": checks, "error": "Domain directory not found"}, False, imported_modules, fully_qualified_symbols

        checks["directory_exists"] = True

        # Check __init__.py existence
        if (domain_path / "__init__.py").exists():
            checks["init_exists"] = True
        else:
            domain_passed = False

        manifest_path = domain_path / "manifest.py"
        if not manifest_path.exists():
            return {"status": "FAIL", "checks": checks, "error": "Missing manifest.py"}, False, imported_modules, fully_qualified_symbols

        checks["manifest_exists"] = True
        manifest_data = self._parse_manifest_safely(manifest_path)

        # Validate DOMAIN_NAME match
        if manifest_data.get("DOMAIN_NAME") == domain_name:
            checks["domain_name_matches"] = True
        else:
            domain_passed = False

        # Validate VERSION declaration
        if "VERSION" in manifest_data:
            checks["version_declared"] = True
        else:
            domain_passed = False

        # Validate Public API definition
        public_api = manifest_data.get("PUBLIC_API", {})
        if public_api:
            checks["public_api_defined"] = True
        else:
            domain_passed = False

        forbidden_imports = manifest_data.get("FORBIDDEN_IMPORTS", [])

        # Extract symbols (modules, classes, methods) via AST across all real python files
        for py_file in domain_path.rglob("*.py"):
            if py_file.name == "manifest.py":
                continue
            file_symbols, file_imports = self._inspect_python_file_ast(py_file, domain_name)
            fully_qualified_symbols.update(file_symbols)
            imported_modules.update(file_imports)

        # Verify every PUBLIC_API entry resolves to an actual symbol in the AST index
        api_targets = public_api.values() if isinstance(public_api, dict) else public_api
        for target in api_targets:
            if target not in fully_qualified_symbols:
                checks["public_api_symbols_resolve"] = False
                domain_passed = False

        status = "PASS" if domain_passed else "FAIL"
        return {
            "status": status,
            "checks": checks,
            "public_api": public_api,
            "forbidden_imports_list": forbidden_imports,
            "detected_imports": list(imported_modules)
        }, domain_passed, imported_modules, fully_qualified_symbols

    def _parse_manifest_safely(self, manifest_path: Path) -> Dict[str, Any]:
        data = {}
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(manifest_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                key = target.id
                                try:
                                    data[key] = ast.literal_eval(node.value)
                                except ValueError:
                                    pass
        except Exception:
            pass
        return data

    def _inspect_python_file_ast(self, file_path: Path, domain_name: str) -> Tuple[Set[str], Set[str]]:
        """
        Extracts fully-qualified symbols including module functions, classes, 
        and instance/class methods (e.g. portfolio_control_plane.PortfolioControlPlane.run_cycle).
        """
        symbols = set()
        imports = set()
        module_name = file_path.stem  # e.g., portfolio_control_plane

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(file_path))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split(".")[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split(".")[0])

                # Walk top-level definitions to construct fully qualified paths
                for node in tree.body:
                    if isinstance(node, ast.FunctionDef):
                        # Module-level function: module_name.func_name
                        symbols.add(f"{module_name}.{node.name}")
                    elif isinstance(node, ast.ClassDef):
                        class_name = node.name
                        # Class path: module_name.ClassName
                        symbols.add(f"{module_name}.{class_name}")
                        
                        # Inspect methods inside the class
                        for subnode in node.body:
                            if isinstance(subnode, ast.FunctionDef):
                                method_name = subnode.name
                                # Method path: module_name.ClassName.method_name
                                symbols.add(f"{module_name}.{class_name}.{method_name}")
                    elif isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                symbols.add(f"{module_name}.{target.id}")
        except SyntaxError:
            pass

        return symbols, imports

    def _detect_cycles(self, graph: Dict[str, Set[str]]) -> Tuple[bool, List[str]]:
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, set()):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    path.append(neighbor)
                    return True

            rec_stack.remove(node)
            path.pop()
            return False

        for node in graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False, []

if __name__ == "__main__":
    verifier = InstitutionalStaticArchitectureVerifier(project_root=".")
    audit_results = verifier.verify_all()
    
    import json
    print(json.dumps(audit_results, indent=2))
    
    if not audit_results.get("passed", False):
        raise SystemExit(1)
