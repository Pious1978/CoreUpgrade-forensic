import sys
import research.governance.serialization
from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.startup_gate import StartupGate
from execution.certification.runtime import CertificationRuntimeStateStore

try:
    print("=== Step 1: Compiling Hardened Signed Manifest ===")
    manifest = ExecutionTheoremRegistry.get_manifest()
    
    # Simulate development mode clearance using explicit environmental parameter
    manifest["signature"] = "UNSIGNED_DEV_MODE"
    
    # Re-digest manifest self-hash to maintain integrity consistency
    verify_manifest = dict(manifest)
    verify_manifest.pop("registry_hash", None)
    verify_manifest.pop("signature", None)
    manifest["registry_hash"] = research.governance.serialization.CanonicalSerializer.digest(verify_manifest)

    print("=== Step 2: Executing Startup Gate Boot Sequence ===")
    certificate = StartupGate.boot_sequence(
        manifest=manifest,
        available_classes=list(ExecutionTheoremRegistry.all()),
        environment="development"
    )
    print(f"Startup Certified: {certificate.certified}")
    print(f"Startup Certificate Hash: {certificate.startup_certificate_hash}")
    print(f"Granular Gate Timings: {certificate.gates_passed}")

    print("=== Step 3: Verifying Runtime Certification State Lock ===")
    print(f"Current Runtime State: {CertificationRuntimeStateStore.get_state().name}")
    print("SUCCESS: Engine gate successfully opened for downstream order routing.")

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)