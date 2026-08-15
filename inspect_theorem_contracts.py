import inspect

from execution.certification.registry import ExecutionTheoremRegistry

for theorem in ExecutionTheoremRegistry.all():
    print("=" * 70)
    print(theorem.__name__)
    print("ID      :", getattr(theorem, "id", None))
    print("verify  :", inspect.signature(theorem.verify))
    print("abstract:", inspect.isabstract(theorem))
    print("depends :", getattr(theorem, "depends_on", ()))
