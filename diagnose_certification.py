from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.registry.manifest import ManifestBuilder
from execution.certification.engine.dependency._resolver import DependencyResolver
from execution.certification.engine.theorem._executor import TheoremExecutor
from execution.manifest import EXECUTION_ENGINE_VERSION

registry = ExecutionTheoremRegistry.all()

manifest = ManifestBuilder.compile(
    registry,
    signing_mode="development",
)

sorted_theorems, dag_hash = DependencyResolver.resolve_topological_sort(registry)

results, diagnostics, execution_order, passed, failed = (
    TheoremExecutor.execute_suite(
        sorted_theorems,
        EXECUTION_ENGINE_VERSION,
    )
)

print()
print("=" * 80)
print(f"PASSED = {passed}")
print(f"FAILED = {failed}")
print("=" * 80)

for theorem_id, result in results.items():
    proof = result["proof"]

    print()
    print(theorem_id)
    print("-" * 80)

    for key, value in proof.items():
        print(f"{key}: {value}")

print()
print("=" * 80)
print("DIAGNOSTICS")
print("=" * 80)

for theorem_id, diagnostic in dict(diagnostics).items():
    print(theorem_id)
    print(diagnostic)
