from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parent

EXCLUDED_DIRS = {
    "__pycache__",
    "_deprecated",
    "_backup",
    "certification_P2_backup",
    "Obsolete",
}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TARGET_SYMBOLS = {
    "ExecutionIntent",
    "ExecutionIntentContract",
    "OrderIntentContract",
    "ExecutionPlanContract",
    "ExecutionResultContract",
    "ExecutionGateway",
    "OrderManager",
    "BrokerAdapter",
    "BrokerInterface",
    "PaperBroker",
    "VSCPipeline",
    "PromotionGraph",
    "DecisionToExecution",
    "ExecutionToResult",
}

TARGET_MODULES = {
    "execution.gateway",
    "execution.events.gateway",
    "execution.contracts.execution_intent",
    "execution.contracts.order_contract",
    "execution.contracts.broker_submission_contract",
    "execution.ems.base_adapter",
    "execution.ems.paper_adapter",
    "execution.oms.order_manager",

    "oms.contracts.order_intent",
    "oms.engine.execution_engine",
    "oms.engine.order_management_engine",
    "oms.services.order_execution_service",

    "brokers.broker_interface",
    "brokers.paper.broker_adapter",
    "brokers.paper.paper_broker",

    "contracts.broker.broker_interface",
    "contracts.execution",

    "vsc.pipeline",
    "vsc.broker",

    "promotion.implementations.decision_to_execution",
    "promotion.implementations.execution_to_result",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def iter_python_files():
    for path in ROOT.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        yield path


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT)

    if relative.name == "__init__.py":
        parts = relative.parts[:-1]
    else:
        parts = relative.with_suffix("").parts

    return ".".join(parts)


def read_ast(path: Path):
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        print(f"SYNTAX ERROR: {rel(path)}: {exc}")
        return None


def dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = dotted_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"

    return None


def imported_symbols(tree):
    result = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append({
                    "kind": "import",
                    "module": alias.name,
                    "name": alias.asname or alias.name.split(".")[0],
                    "line": node.lineno,
                })

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""

            if node.level:
                prefix = "." * node.level
                module = prefix + module

            for alias in node.names:
                result.append({
                    "kind": "from",
                    "module": module,
                    "name": alias.name,
                    "line": node.lineno,
                })

    return result


def definitions(tree):
    result = []

    for node in ast.walk(tree):

        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            result.append({
                "name": node.name,
                "kind": type(node).__name__,
                "line": node.lineno,
            })

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result.append({
                        "name": target.id,
                        "kind": "assignment",
                        "line": node.lineno,
                    })

    return result


# ---------------------------------------------------------------------------
# 1. FILE / MODULE COLLISIONS
# ---------------------------------------------------------------------------

def trace_module_collisions():

    print("=" * 110)
    print("1. MODULE / PACKAGE COLLISIONS")
    print("=" * 110)

    packages = defaultdict(lambda: {"files": [], "packages": []})

    for path in iter_python_files():

        relpath = path.relative_to(ROOT)

        if relpath.name == "__init__.py":
            continue

        parts = relpath.with_suffix("").parts

        if len(parts) < 1:
            continue

        module = ".".join(parts)
        packages[module]["files"].append(rel(path))

    for path in ROOT.rglob("__init__.py"):

        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue

        relpath = path.relative_to(ROOT)
        module = ".".join(relpath.parts[:-1])

        packages[module]["packages"].append(rel(path))

    collisions = []

    for module, data in packages.items():

        if data["files"] and data["packages"]:
            collisions.append((module, data))

    if not collisions:
        print("No module/package collisions detected.")
        return

    for module, data in sorted(collisions):

        print(f"\nCOLLISION: {module}")

        print("  module file(s):")
        for item in data["files"]:
            print(f"    {item}")

        print("  package initializer(s):")
        for item in data["packages"]:
            print(f"    {item}")

        print("  STATUS: PYTHON IMPORT IDENTITY IS AMBIGUOUS")


# ---------------------------------------------------------------------------
# 2. SYMBOL DEFINITIONS
# ---------------------------------------------------------------------------

def trace_symbol_definitions():

    print("\n" + "=" * 110)
    print("2. SYMBOL DEFINITIONS")
    print("=" * 110)

    definitions_map = defaultdict(list)

    for path in iter_python_files():

        tree = read_ast(path)

        if tree is None:
            continue

        for item in definitions(tree):

            if item["name"] in TARGET_SYMBOLS:

                definitions_map[item["name"]].append(
                    (
                        rel(path),
                        item["kind"],
                        item["line"],
                    )
                )

    for symbol in sorted(TARGET_SYMBOLS):

        print(f"\nSYMBOL: {symbol}")

        matches = definitions_map.get(symbol)

        if not matches:
            print("  NOT DEFINED")
            continue

        for file, kind, line in matches:
            print(f"  {kind:<15} {file}:{line}")

        if len(matches) > 1:
            print("  !!! DUPLICATE DEFINITIONS !!!")


# ---------------------------------------------------------------------------
# 3. IMPORTS INVOLVING TARGET SYMBOLS
# ---------------------------------------------------------------------------

def trace_symbol_imports():

    print("\n" + "=" * 110)
    print("3. IMPORTS OF TARGET SYMBOLS")
    print("=" * 110)

    found = []

    for path in iter_python_files():

        tree = read_ast(path)

        if tree is None:
            continue

        for item in imported_symbols(tree):

            if item["name"] in TARGET_SYMBOLS:

                found.append(
                    (
                        rel(path),
                        item["line"],
                        item["kind"],
                        item["module"],
                        item["name"],
                    )
                )

    for file, line, kind, module, name in found:

        if kind == "from":
            statement = f"from {module} import {name}"
        else:
            statement = f"import {module}"

        print(f"{file}:{line}")
        print(f"  {statement}")


# ---------------------------------------------------------------------------
# 4. DIRECT SYMBOL REFERENCES
# ---------------------------------------------------------------------------

def trace_symbol_references():

    print("\n" + "=" * 110)
    print("4. DIRECT SYMBOL REFERENCES / CONSTRUCTION")
    print("=" * 110)

    for path in iter_python_files():

        tree = read_ast(path)

        if tree is None:
            continue

        matches = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Name):
                if node.id in TARGET_SYMBOLS:
                    matches.append((node.id, node.lineno, "Name"))

            elif isinstance(node, ast.Attribute):
                if node.attr in TARGET_SYMBOLS:
                    matches.append((node.attr, node.lineno, "Attribute"))

        if matches:

            print(f"\n{rel(path)}")

            seen = set()

            for symbol, line, kind in matches:

                key = (symbol, line)

                if key in seen:
                    continue

                seen.add(key)

                print(f"  line {line:<5} {kind:<10} {symbol}")


# ---------------------------------------------------------------------------
# 5. IMPORT GRAPH FOR EXECUTION / OMS / BROKERS / PROMOTION / VSC
# ---------------------------------------------------------------------------

def trace_architecture_import_graph():

    print("\n" + "=" * 110)
    print("5. ARCHITECTURE IMPORT GRAPH")
    print("=" * 110)

    prefixes = (
        "execution",
        "oms",
        "brokers",
        "contracts",
        "promotion",
        "vsc",
    )

    for path in iter_python_files():

        mod = module_name(path)

        if not mod.startswith(prefixes):
            continue

        tree = read_ast(path)

        if tree is None:
            continue

        imports = imported_symbols(tree)

        relevant = []

        for item in imports:

            target = item["module"].lstrip(".")

            if target.startswith(prefixes):
                relevant.append(item)

        if not relevant:
            continue

        print(f"\n{mod}")
        print(f"  FILE: {rel(path)}")

        for item in relevant:

            if item["kind"] == "from":
                print(
                    f"  line {item['line']:<4} "
                    f"FROM {item['module']} "
                    f"IMPORT {item['name']}"
                )
            else:
                print(
                    f"  line {item['line']:<4} "
                    f"IMPORT {item['module']}"
                )


# ---------------------------------------------------------------------------
# 6. BROKER INTERFACE TRACE
# ---------------------------------------------------------------------------

def trace_broker_interfaces():

    print("\n" + "=" * 110)
    print("6. BROKER INTERFACE TRACE")
    print("=" * 110)

    candidates = [
        ROOT / "brokers" / "broker_interface.py",
        ROOT / "contracts" / "broker" / "broker_interface.py",
        ROOT / "execution" / "broker_interface.py",
    ]

    for path in candidates:

        print(f"\n{rel(path)}")

        if not path.exists():
            print("  DOES NOT EXIST")
            continue

        tree = read_ast(path)

        if tree is None:
            continue

        for item in definitions(tree):

            if "Broker" in item["name"] or "Adapter" in item["name"]:
                print(
                    f"  {item['kind']:<15} "
                    f"{item['name']}:{item['line']}"
                )

    print("\nIMPORTS CONTAINING broker_interface:")

    for path in iter_python_files():

        tree = read_ast(path)

        if tree is None:
            continue

        for item in imported_symbols(tree):

            if "broker_interface" in item["module"].lower():

                print(
                    f"  {rel(path)}:{item['line']} "
                    f"{item['module']}"
                )


# ---------------------------------------------------------------------------
# 7. EXECUTION CONTRACT FAMILY
# ---------------------------------------------------------------------------

def trace_execution_contract_family():

    print("\n" + "=" * 110)
    print("7. EXECUTION CONTRACT FAMILY")
    print("=" * 110)

    candidates = [
        ROOT / "contracts" / "execution.py",
        ROOT / "contracts" / "execution",
        ROOT / "execution" / "contracts",
        ROOT / "oms" / "contracts",
    ]

    for path in candidates:

        print(f"\n{rel(path)}")

        if not path.exists():
            print("  DOES NOT EXIST")
            continue

        if path.is_file():

            tree = read_ast(path)

            if tree is None:
                continue

            for item in definitions(tree):

                if "Execution" in item["name"] or "Order" in item["name"]:
                    print(
                        f"  {item['kind']:<15} "
                        f"{item['name']}:{item['line']}"
                    )

        else:

            for child in sorted(path.rglob("*.py")):

                if any(part in EXCLUDED_DIRS for part in child.parts):
                    continue

                tree = read_ast(child)

                if tree is None:
                    continue

                names = [
                    x["name"]
                    for x in definitions(tree)
                    if "Execution" in x["name"]
                    or "Order" in x["name"]
                ]

                if names:

                    print(f"  {rel(child)}")

                    for name in names:
                        print(f"    {name}")


# ---------------------------------------------------------------------------
# 8. PROMOTION -> EXECUTION TRACE
# ---------------------------------------------------------------------------

def trace_promotion_execution():

    print("\n" + "=" * 110)
    print("8. PROMOTION -> EXECUTION TRACE")
    print("=" * 110)

    promotion_files = [
        ROOT / "promotion" / "implementations" / "decision_to_execution.py",
        ROOT / "promotion" / "implementations" / "execution_to_result.py",
    ]

    for path in promotion_files:

        print(f"\nFILE: {rel(path)}")

        if not path.exists():
            print("  DOES NOT EXIST")
            continue

        tree = read_ast(path)

        if tree is None:
            continue

        print("  IMPORTS:")

        for item in imported_symbols(tree):

            print(
                f"    line {item['line']:<4} "
                f"{item['kind']:<5} "
                f"{item['module']} "
                f"{item['name']}"
            )

        print("  DEFINITIONS:")

        for item in definitions(tree):

            print(
                f"    {item['kind']:<15} "
                f"{item['name']}:{item['line']}"
            )


# ---------------------------------------------------------------------------
# 9. EXECUTION / OMS / EMS FILE INVENTORY
# ---------------------------------------------------------------------------

def trace_execution_components():

    print("\n" + "=" * 110)
    print("9. EXECUTION / OMS / EMS COMPONENT INVENTORY")
    print("=" * 110)

    roots = [
        ROOT / "execution",
        ROOT / "oms",
        ROOT / "brokers",
    ]

    for base in roots:

        print(f"\n[{rel(base)}]")

        if not base.exists():
            continue

        for path in sorted(base.rglob("*.py")):

            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue

            name = path.name.lower()

            if any(
                token in name
                for token in (
                    "execution",
                    "order",
                    "gateway",
                    "broker",
                    "adapter",
                    "intent",
                    "ems",
                    "oms",
                )
            ):

                print(f"  {rel(path)}")


# ---------------------------------------------------------------------------
# 10. SUMMARY / FORENSIC FINDINGS
# ---------------------------------------------------------------------------

def forensic_summary():

    print("\n" + "=" * 110)
    print("10. PRELIMINARY FORENSIC FINDINGS")
    print("=" * 110)

    print("""
[DO NOT MODIFY CODE BASED ON THIS SECTION]

The static trace is intended to establish architecture before remediation.

Questions to answer from the output:

1. Which ExecutionIntent definition is actually upstream of execution?

2. Is ExecutionPlanContract a live contract or a legacy/shadow contract?

3. Is ExecutionResultContract part of the live execution path or merely
   a compatibility/legacy contract?

4. Which BrokerInterface is consumed by the live EMS/broker path?

5. Is brokers.broker_interface canonical, or is
   contracts.broker.broker_interface canonical?

6. Is execution.gateway part of the live path, or is it an orphaned/obsolete
   implementation?

7. Which component consumes ExecutionIntent?

8. Where is ExecutionIntent converted into OrderIntentContract?

9. Where is OrderIntentContract converted into an executable order?

10. Which component actually calls a broker/EMS adapter?

11. Does promotion/implementations/decision_to_execution.py feed the same
    execution path as the OMS/EMS stack?

12. Is vsc.pipeline a live production path or a parallel test/demo path?

13. Does execution_to_result.py consume the actual broker execution result?

14. Are there multiple independent execution pipelines?

15. Where is the FIRST point at which the architectural graph becomes
    disconnected?

The goal is to identify ONE canonical path, not to repair individual import
errors independently.
""")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():

    print("=" * 110)
    print("CoreUpgrade - STATIC EXECUTION ARCHITECTURE FORENSIC TRACE")
    print("=" * 110)
    print(f"Repository root: {ROOT}")
    print(f"Python: {sys.version}")

    trace_module_collisions()
    trace_symbol_definitions()
    trace_symbol_imports()
    trace_symbol_references()
    trace_architecture_import_graph()
    trace_broker_interfaces()
    trace_execution_contract_family()
    trace_promotion_execution()
    trace_execution_components()
    forensic_summary()


if __name__ == "__main__":
    main()