from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.registry.manifest import ManifestBuilder
from execution.certification.startup_gate import StartupGate


def test_boot_sequence():
    registry = ExecutionTheoremRegistry.all()

    manifest = ManifestBuilder.compile(
        registry,
        signing_mode="development",
    )

    assert manifest["manifest_id"] == "EXECUTION-THEOREM-REGISTRY"
    assert manifest["registry_hash"]
    assert manifest["signature"] == "UNSIGNED_DEV_MODE"

    certificate = StartupGate.boot_sequence(
        manifest=manifest,
        registry=registry,
        environment="development",
    )

    assert certificate is not None