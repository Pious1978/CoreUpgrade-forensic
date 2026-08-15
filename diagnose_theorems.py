from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.registry.manifest import ManifestBuilder
from execution.certification.engine.theorem._executor import TheoremExecutor
from execution.certification.engine.dependency._resolver import DependencyResolver
from execution.certification.startup_gate import EXECUTION_ENGINE_VERSION


registry = ExecutionTheoremRegistry.all()

manifest = ManifestBuilder.compile(
    registry,
    signing_mode="development",
)

sorted_theorems, dag_hash = DependencyResolver.resolve_topological_sort(
    registry
)

results, diagnostics, execution_order, passed, failed = (
    TheoremExecutor.execute_suite(
        sorted_theorems,
        EXECUTION_ENGINE_VERSION,
    )
)

print()
print("==============================================")
print(" THEOREM EXECUTION DIAGNOSTIC")
print("==============================================")
print(f"Total   : {len(sorted_theorems)}")
print(f"Passed  : {passed}")
print(f"Failed  : {failed}")
print()

for theorem_id in execution_order:
    proof = results[theorem_id]["proof"]

    if not proof.get("certified", False):
        print("----------------------------------------------")
        print(f"THEOREM : {theorem_id}")
        print(f"Failure : {proof.get('failure_type')}")
        print(f"Origin  : {proof.get('failure_origin')}")
        print(f"Severity: {proof.get('severity')}")
        print(f"Reason  : {proof.get('reason_code')}")
        print(f"Detail  : {proof.get('reason')}")

        if theorem_id in diagnostics:
            print("Diagnostics:")
            print(dict(diagnostics[theorem_id]))
