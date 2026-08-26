from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def header(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def show_module(module_name: str) -> None:
    header(f"MODULE: {module_name}")

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        print(f"IMPORT ERROR: {type(exc).__name__}: {exc}")
        return

    print(f"__file__ : {getattr(module, '__file__', None)}")
    print(f"__package__: {getattr(module, '__package__', None)}")

    public_names = [
        name for name in dir(module)
        if not name.startswith("_")
    ]

    print("\nRelevant exported names:")
    for name in public_names:
        if any(
            token in name.lower()
            for token in (
                "execution",
                "order",
                "promotion",
                "intent",
                "plan",
                "result",
            )
        ):
            obj = getattr(module, name, None)

            try:
                obj_file = inspect.getfile(obj)
            except (TypeError, OSError):
                obj_file = None

            print(
                f"  {name:<35} "
                f"type={type(obj).__name__:<20} "
                f"module={getattr(obj, '__module__', None)} "
                f"file={obj_file}"
            )


def show_class(module_name: str, class_name: str) -> None:
    header(f"CLASS: {module_name}.{class_name}")

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        print(f"IMPORT ERROR: {type(exc).__name__}: {exc}")
        return

    cls = getattr(module, class_name, None)

    if cls is None:
        print("NOT FOUND")
        return

    print(f"class object : {cls!r}")
    print(f"__module__   : {cls.__module__}")
    print(f"__qualname__ : {cls.__qualname__}")

    try:
        print(f"source file  : {inspect.getfile(cls)}")
    except (TypeError, OSError) as exc:
        print(f"source file  : unavailable ({exc})")

    try:
        print(f"signature    : {inspect.signature(cls)}")
    except (TypeError, ValueError) as exc:
        print(f"signature    : unavailable ({exc})")

    print("\nMRO:")
    for base in cls.__mro__:
        print(f"  {base!r}")

    annotations = getattr(cls, "__annotations__", {})
    if annotations:
        print("\nAnnotations:")
        for name, value in annotations.items():
            print(f"  {name}: {value}")

    print("\nDataclass fields:")
    fields = getattr(cls, "__dataclass_fields__", {})
    for name, field in fields.items():
        print(
            f"  {name}: "
            f"type={field.type!r}, "
            f"default={field.default!r}, "
            f"default_factory={field.default_factory!r}"
        )


def trace_promotion() -> None:
    header("PROMOTION IMPLEMENTATION: decision_to_execution")

    module_name = "promotion.implementations.decision_to_execution"

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        print(f"IMPORT ERROR: {type(exc).__name__}: {exc}")
        return

    print(f"module file: {module.__file__}")

    for name in dir(module):
        if name.startswith("_"):
            continue

        obj = getattr(module, name)

        if inspect.isclass(obj):
            if any(
                token in name.lower()
                for token in (
                    "promotion",
                    "execution",
                    "decision",
                    "promoter",
                )
            ):
                print(f"\nCLASS: {name}")
                print(f"  module    : {obj.__module__}")

                try:
                    print(f"  source    : {inspect.getfile(obj)}")
                except (TypeError, OSError):
                    pass

                try:
                    print(f"  signature : {inspect.signature(obj)}")
                except (TypeError, ValueError):
                    pass

                for method_name in (
                    "transform",
                    "promote",
                    "apply",
                    "execute",
                ):
                    method = getattr(obj, method_name, None)
                    if method is not None:
                        print(f"\n  METHOD: {method_name}")
                        try:
                            print(
                                inspect.getsource(method)
                            )
                        except (OSError, TypeError) as exc:
                            print(f"    source unavailable: {exc}")


def trace_execution_graph() -> None:
    header("EXECUTION MODULE GRAPH")

    module_names = [
        "contracts.execution",
        "contracts.execution.execution_plan",
        "contracts.execution.execution_result",
        "execution.contracts.execution_intent",
        "execution.contracts.order_contract",
        "oms.contracts.order_intent",
        "execution.gateway",
        "execution.oms.order_manager",
        "oms.engine.execution_engine",
        "oms.engine.order_management_engine",
        "oms.services.order_execution_service",
        "vsc.pipeline",
        "vsc.broker",
    ]

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)

            print(
                f"{module_name:<50} "
                f"→ {getattr(module, '__file__', None)}"
            )

        except Exception as exc:
            print(
                f"{module_name:<50} "
                f"→ IMPORT ERROR: {type(exc).__name__}: {exc}"
            )


def trace_vsc_contract_identity() -> None:
    header("VSC CONTRACT IDENTITY")

    try:
        vsc = importlib.import_module("vsc.pipeline")
    except Exception as exc:
        print(f"VSC IMPORT ERROR: {type(exc).__name__}: {exc}")
        return

    for name in (
        "ExecutionPlanContract",
        "ExecutionResultContract",
    ):
        obj = getattr(vsc, name, None)

        print(f"\n{name}")
        print(f"  object : {obj!r}")

        if obj is None:
            continue

        print(f"  module : {obj.__module__}")

        try:
            print(f"  file   : {inspect.getfile(obj)}")
        except (TypeError, OSError):
            pass

    print("\nVSC pipeline module:")
    print(f"  {vsc.__file__}")


def trace_sys_path() -> None:
    header("PYTHON IMPORT PATH")

    for index, path in enumerate(sys.path):
        print(f"{index:02d}: {path}")


def main() -> None:
    print("=" * 100)
    print("CoreUpgrade — READ-ONLY EXECUTION ARCHITECTURE FORENSIC TRACE")
    print("=" * 100)
    print(f"Repository root: {ROOT}")
    print(f"Python: {sys.version}")

    trace_sys_path()

    trace_execution_graph()

    show_module("contracts.execution")

    show_class(
        "contracts.execution",
        "ExecutionPlanContract",
    )

    show_class(
        "contracts.execution",
        "ExecutionResultContract",
    )

    show_class(
        "contracts.execution.execution_plan",
        "ExecutionPlanContract",
    )

    show_class(
        "contracts.execution.execution_result",
        "ExecutionResultContract",
    )

    show_class(
        "execution.contracts.execution_intent",
        "ExecutionIntent",
    )

    show_class(
        "execution.contracts.order_contract",
        "OrderContract",
    )

    show_class(
        "oms.contracts.order_intent",
        "OrderIntentContract",
    )

    trace_promotion()

    trace_vsc_contract_identity()


if __name__ == "__main__":
    main()