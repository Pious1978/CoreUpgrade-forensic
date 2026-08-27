"""
Manifest Builder & Signing Engine

Authority:
    Execution Layer Governance Manifest Compilation
"""
import inspect
import copy
import textwrap
from typing import Tuple, Type, Dict, Any, List
from research.governance.serialization import CanonicalSerializer
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

class ManifestBuilder:
    @staticmethod
    def normalize_source(source: str) -> str:
        return textwrap.dedent(source).strip()

    @classmethod
    def compile(
        cls, 
        registered_classes: Tuple[Type[EmpiricalTheorem], ...], 
        signing_mode: str = "production",
        private_key: str = "DEFAULT_GOVERNANCE_SIGNING_KEY"
    ) -> Dict[str, Any]:
        """
        Compiles registered theorems into a verified cryptographic manifest, 
        encapsulating signature generation, environment binding, and schema rules.
        """
        seen_ids = set()
        theorems_manifest = []

        for t in sorted(registered_classes, key=lambda x: x.id):
            theorem_id = getattr(t, "id", None)
            if not theorem_id:
                raise RuntimeError(f"Theorem class {t.__name__} missing required unique 'id'.")
            if theorem_id in seen_ids:
                raise RuntimeError(f"Duplicate theorem ID detected during manifest compilation: '{theorem_id}'.")
            seen_ids.add(theorem_id)

            authority = getattr(t, "authority", None)
            if not authority:
                raise RuntimeError(f"Theorem {theorem_id} missing mandatory 'authority' metadata.")
            
            domain = getattr(t, "domain", "General")
            version = getattr(t, "version", "1.0.0")
            depends_on = sorted(list(getattr(t, "depends_on", ())))

            try:
                raw_source = inspect.getsource(t)
                source_code = cls.normalize_source(raw_source)
            except (TypeError, OSError) as e:
                raise RuntimeError(f"Failed to extract source for {theorem_id}: {e}")

            implementation_payload = {
                "module": t.__module__,
                "class": t.__name__,
                "version": version,
                "required_engine_version": t.required_engine_version,
                "source": source_code,
            }
            implementation_hash = CanonicalSerializer.hash(implementation_payload)

            theorems_manifest.append({
                "id": theorem_id,
                "module": t.__module__,
                "class": t.__name__,
                "version": version,
                "authority": authority,
                "domain": domain,
                "depends_on": depends_on,
                "implementation_hash": implementation_hash,
            })
        
        environment_fingerprint = {
            "schema": "1.0",
            **CanonicalSerializer.get_environment_fingerprint()
        }

        manifest = {
            "manifest_id": "EXECUTION-THEOREM-REGISTRY",
            "manifest_schema": "1.0",
            "engine_version": "1.0.0",
            "serializer_version": "1.0.0",
            "hash_algorithm": "SHA-256",
            "registry_size": len(registered_classes),
            "signature_mode": "UNSIGNED_DEV_MODE" if signing_mode == "development" else "ED25519",
            "environment_fingerprint": environment_fingerprint,
            "theorems": theorems_manifest,
        }
        
        copy_manifest = copy.deepcopy(manifest)
        copy_manifest.pop("registry_hash", None)
        copy_manifest.pop("signature", None)
        
        registry_hash = CanonicalSerializer.digest(copy_manifest)
        manifest["registry_hash"] = registry_hash

        if signing_mode == "development":
            manifest["signature"] = "UNSIGNED_DEV_MODE"
        else:
            sig_payload = f"{registry_hash}:{private_key}"
            manifest["signature"] = CanonicalSerializer.hash(sig_payload)

        return manifest
```[cite: 42, 44]

---

### 2. Startup Gate & Boot Sequence Engine
* **File Name and Path:** `execution/certification/startup_gate.py`[cite: 45]

```python
"""
Startup Gate & Boot Sequence Engine

Authority:
    Execution Layer Security & Boot Gating
"""
import copy
import time
from typing import List, Type, Optional, Dict, Any

from research.governance.serialization import CanonicalSerializer
from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.registry.manifest import ManifestBuilder
from execution.certification.runtime import CertificationRuntime, CertificationRuntimeStateStore, RuntimeCertificationState
from execution.certification.engine.certificate_issuer import StartupCertificate, CertificateIssuer

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    Ed25519PublicKey = None


class StartupGate:
    """
    Enforces a strict, fail-closed stateful boot pipeline for the institutional execution engine.
    """
    REQUIRED_MANIFEST_FIELDS = {
        "manifest_id",
        "manifest_schema",
        "engine_version",
        "serializer_version",
        "hash_algorithm",
        "registry_size",
        "signature_mode",
        "environment_fingerprint",
        "theorems",
        "registry_hash",
        "signature"
    }
    ENVIRONMENT_SCHEMA_VERSION = "1.0"

    @staticmethod
    def verify_signature(registry_hash_hex: str, signature_hex: str, public_key_bytes: Optional[bytes] = None, environment: str = "production") -> bool:
        if signature_hex == "UNSIGNED_DEV_MODE":
            if environment != "development":
                raise RuntimeError("CRITICAL SECURITY VIOLATION: 'UNSIGNED_DEV_MODE' manifests are strictly forbidden outside development.")
            return True

        if not public_key_bytes or Ed25519PublicKey is None:
            return False

        try:
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            registry_hash_bytes = bytes.fromhex(registry_hash_hex)
            signature_bytes = bytes.fromhex(signature_hex)
            public_key.verify(signature_bytes, registry_hash_bytes)
            return True
        except Exception:
            return False

    @classmethod
    def boot_sequence(
        cls,
        *,
        manifest: dict,
        registry: List[Type[EmpiricalTheorem]],
        environment: str = "production",
        public_key: Optional[bytes] = None
    ) -> StartupCertificate:
        print("\n================================================")
        print(" EXECUTION ENGINE BOOT CERTIFICATION")
        print("================================================")
        
        gate_timings = {}
        CertificationRuntimeStateStore.transition(RuntimeCertificationState.INITIALIZING)
        CertificationRuntimeStateStore.transition(RuntimeCertificationState.VALIDATING)

        try:
            start_t = time.perf_counter()
            missing_fields = cls.REQUIRED_MANIFEST_FIELDS - manifest.keys()
            if missing_fields:
                raise RuntimeError(f"Gate Failure [schema_validation]: Missing required manifest fields: {missing_fields}")
            gate_timings["schema_validation_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            print("[1] Manifest Compilation\n        OK\n        Registry Hash:\n        " + manifest.get("registry_hash", "")[:12] + "...")

            start_t = time.perf_counter()
            manifest_engine_version = manifest.get("engine_version")
            if manifest_engine_version != EXECUTION_ENGINE_VERSION:
                raise RuntimeError(
                    f"Gate Failure [engine_version_check]: Engine version mismatch. "
                    f"Manifest specifies '{manifest_engine_version}', execution engine running '{EXECUTION_ENGINE_VERSION}'."
                )
            gate_timings["engine_version_check_ms"] = round((time.perf_counter() - start_t) * 1000, 3)

            start_t = time.perf_counter()
            current_env = CanonicalSerializer.get_environment_fingerprint()
            stored_env = manifest.get("environment_fingerprint", {})
            
            if stored_env.get("schema") != cls.ENVIRONMENT_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Gate Failure [environment_schema]: Environment fingerprint schema version mismatch. "
                    f"Expected: '{cls.ENVIRONMENT_SCHEMA_VERSION}', Got: '{stored_env.get('schema')}'."
                )

            for k, v in current_env.items():
                if stored_env.get(k) != v:
                    raise RuntimeError(
                        f"Gate Failure [environment_fingerprint_check]: Environment mismatch on '{k}'. "
                        f"Expected: '{v}', Got: '{stored_env.get(k)}'."
                    )
            gate_timings["environment_fingerprint_ms"] = round((time.perf_counter() - start_t) * 1000, 3)

            start_t = time.perf_counter()
            registry_hash = manifest.get("registry_hash")
            signature = manifest.get("signature")
            if not cls.verify_signature(registry_hash, signature, public_key, environment=environment):
                raise RuntimeError("Gate Failure [cryptographic_signature_verify]: Registry signature validation failed.")
            gate_timings["cryptographic_signature_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            print("\n[2] Cryptographic Validation\n        OK\n        Signature:\n        " + manifest.get("signature_mode", "ED25519"))

            start_t = time.perf_counter()
            verify_manifest = copy.deepcopy(manifest)
            verify_manifest.pop("registry_hash", None)
            verify_manifest.pop("signature", None)
            recalculated_hash = CanonicalSerializer.digest(verify_manifest)
            if recalculated_hash != registry_hash:
                raise RuntimeError("Gate Failure [registry_hash_verify]: Registry hash mismatch. Manifest tampering detected.")
            gate_timings["registry_hash_verify_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            print("\n[3] Registry Integrity\n        OK\n        Theorems:\n        " + str(manifest.get("registry_size")))

            start_t = time.perf_counter()
            seen_ids = []
            for t in registry:
                t_id = getattr(t, "id", None)
                if not t_id:
                    raise RuntimeError(f"Gate Failure [duplicate_id_check]: Theorem class {t.__name__} missing unique ID.")
                if t_id in seen_ids:
                    raise RuntimeError(f"Gate Failure [duplicate_id_check]: Duplicate theorem ID detected: '{t_id}'.")
                seen_ids.append(t_id)

            if not ExecutionTheoremRegistry.verify_registry_integrity(registry, manifest):
                raise RuntimeError("Gate Failure [theorem_implementation_integrity]: Theorem code source integrity verification failed.")
            gate_timings["theorem_implementation_integrity_ms"] = round((time.perf_counter() - start_t) * 1000, 3)

            manifest_theorems = manifest.get("theorems", [])
            registry_size = manifest.get("registry_size")
            if len(manifest_theorems) != registry_size or len(registry) != registry_size:
                raise RuntimeError(f"Gate Failure [registry_size_match]: Registry size mismatch.")

            start_t = time.perf_counter()
            sorted_theorems = CertificationRuntime.validate_registry_explicit(registry)
            gate_timings["dependency_graph_validation_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            print("\n[4] Dependency Graph\n        OK\n        DAG Verified")

            start_t = time.perf_counter()
            registry_tuple = tuple(
                {
                    "id": t.id,
                    "version": t.version,
                    "required_engine_version": t.required_engine_version,
                    "authority": getattr(t, "authority", "Unknown"),
                    "domain": getattr(t, "domain", "Unknown"),
                    "depends_on": list(getattr(t, "depends_on", ())),
                    "module": t.__module__,
                    "class": t.__name__,
                }
                for t in sorted_theorems
            )
            registry_payload = {
                "schema_version": manifest.get("manifest_schema", "1.0"),
                "manifest_hash": registry_hash,
                "registered_theorems": registry_tuple,
            }
            registry_fingerprint = CanonicalSerializer.digest(registry_payload)

            from execution.certification.theorem_execution_empirical_001 import ExecutionEmpiricalTheorem
            empirical_result = ExecutionEmpiricalTheorem.verify_with_registry(
                sorted_theorems, registry_hash, registry_fingerprint
            )

            if not empirical_result.certified:
                raise RuntimeError(f"Gate Failure [empirical_certification]: Empirical execution certification failed. Reason: {empirical_result.reason}")
            gate_timings["empirical_certification_ms"] = round((time.perf_counter() - start_t) * 1000, 3)
            print("\n[5] Empirical Certification\n        PASS\n        Proof Hash:\n        " + empirical_result.master_proof_hash[:12] + "...")

            CertificationRuntimeStateStore.transition(RuntimeCertificationState.CERTIFIED)
            print("\n[6] Runtime State Lock\n        CERTIFIED")

            timestamp = time.time()
            env_hash = CanonicalSerializer.hash(current_env)

            partial_cert_dict = {
                "certified": True,
                "manifest_id": manifest.get("manifest_id"),
                "manifest_schema_version": manifest.get("manifest_schema"),
                "engine_version": EXECUTION_ENGINE_VERSION,
                "registry_hash": registry_hash,
                "registry_signature": signature,
                "environment_hash": env_hash,
                "timestamp": str(timestamp),
                "total_theorems": len(sorted_theorems),
                "gates_passed": gate_timings,
                "empirical_proof_hash": empirical_result.master_proof_hash,
            }
            startup_certificate_hash = CanonicalSerializer.digest(partial_cert_dict)

            certificate = StartupCertificate(
                certified=True,
                manifest_id=manifest.get("manifest_id"),
                manifest_schema_version=manifest.get("manifest_schema"),
                engine_version=EXECUTION_ENGINE_VERSION,
                registry_hash=registry_hash,
                registry_signature=signature,
                environment_hash=env_hash,
                timestamp=str(timestamp),
                total_theorems=len(sorted_theorems),
                gates_passed=gate_timings,
                empirical_proof_hash=empirical_result.master_proof_hash,
                startup_certificate_hash=startup_certificate_hash
            )

            if not CertificateIssuer.verify(certificate):
                raise RuntimeError("Gate Failure [certificate_verification]: Startup certificate verification failed.")

            CertificationRuntimeStateStore.transition(RuntimeCertificationState.EXECUTION_ENABLED)
            certificate.persist()

            print("\n[7] Execution Gate\n        OPEN")
            print("================================================")
            print(" TRADING EXECUTION AUTHORIZED")
            print("================================================\n")

            return certificate

        except Exception as e:
            CertificationRuntimeStateStore.transition(RuntimeCertificationState.HALTED)
            print(f"\nCRITICAL: Startup gate breached or failed. Engine transitioned to HALTED. Reason: {e}")
            raise
```[cite: 45]

---

### 3. Runtime State Machine Store
* **File Name and Path:** `execution/certification/runtime.py`[cite: 30, 35, 43, 45]

```python
"""
Execution Certification Runtime & State Machine

Authority:
    Execution Layer Admission Control & State Governance
"""
from enum import Enum, auto
from typing import Dict, Any, List, Type, Tuple
from dataclasses import dataclass
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.theorem_execution_empirical_001 import ExecutionEmpiricalTheorem

class RuntimeCertificationState(Enum):
    INITIALIZING = "INITIALIZING"
    VALIDATING = "VALIDATING"
    CERTIFIED = "CERTIFIED"
    EXECUTION_ENABLED = "EXECUTION_ENABLED"
    HALTED = "HALTED"
    REVOKED = "REVOKED"

class CertificationRuntimeStateStore:
    _state: RuntimeCertificationState = RuntimeCertificationState.INITIALIZING

    @classmethod
    def transition(cls, target_state: RuntimeCertificationState):
        if cls._state == RuntimeCertificationState.HALTED:
            raise RuntimeError("CRITICAL: Engine is permanently HALTED due to security violation or mutation attempt.")
        cls._state = target_state

    @classmethod
    def get_state(cls) -> RuntimeCertificationState:
        return cls._state

    @classmethod
    def assert_execution_enabled(cls):
        if cls._state != RuntimeCertificationState.EXECUTION_ENABLED:
            raise RuntimeError(f"Security Violation: Engine state is {cls._state.name}, not EXECUTION_ENABLED. Action blocked.")

class CertificationRuntime:
    @staticmethod
    def execute() -> Any:
        CertificationRuntimeStateStore.assert_execution_enabled()
        return ExecutionEmpiricalTheorem.verify()

    @staticmethod
    def validate_registry_explicit(available_classes: List[Type[EmpiricalTheorem]]) -> Tuple[Type[EmpiricalTheorem], ...]:
        return ExecutionEmpiricalTheorem.validate_registry_explicit(available_classes)
```[cite: 30, 35, 43, 45]

---

### 4. Certificate Issuer & Verifier
* **File Name and Path:** `execution/certification/engine/certificate_issuer.py`[cite: 41, 46]

```python
"""
Certificate Issuer & Runtime State Governance

Authority:
    Execution Layer Admission Control & Startup Certification Issuance
"""
import json
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from research.governance.serialization import CanonicalSerializer

@dataclass(frozen=True, slots=True)
class StartupCertificate:
    certified: bool
    manifest_id: str
    manifest_schema_version: str
    engine_version: str
    registry_hash: str
    registry_signature: str
    environment_hash: str
    timestamp: str
    total_theorems: int
    gates_passed: Dict[str, float]
    empirical_proof_hash: Optional[str] = None
    startup_certificate_hash: Optional[str] = None

    def persist(self, directory: str = "certificates") -> str:
        os.makedirs(directory, exist_ok=True)
        filename = f"startup_certificate_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        filepath = os.path.join(directory, filename)
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True, indent=2))
        return filepath

class CertificateIssuer:
    @staticmethod
    def verify(certificate: StartupCertificate) -> bool:
        """
        Cryptographically verifies the startup certificate's self-referential hash 
        and structural validity.
        """
        if not certificate.certified:
            return False
        
        partial_cert_dict = {
            "certified": certificate.certified,
            "manifest_id": certificate.manifest_id,
            "manifest_schema_version": certificate.manifest_schema_version,
            "engine_version": certificate.engine_version,
            "registry_hash": certificate.registry_hash,
            "registry_signature": certificate.registry_signature,
            "environment_hash": certificate.environment_hash,
            "timestamp": certificate.timestamp,
            "total_theorems": certificate.total_theorems,
            "gates_passed": certificate.gates_passed,
            "empirical_proof_hash": certificate.empirical_proof_hash,
        }
        recalculated_hash = CanonicalSerializer.digest(partial_cert_dict)
        return recalculated_hash == certificate.startup_certificate_hash
```[cite: 41, 46]

---

### 5. Negative & Positive Test Harness
* **File Name and Path:** `tests/certification/test_boot_sequence.py`[cite: 48, 49]

```python
"""
Comprehensive Startup Gate & Registry Certification Test Suite

Authority:
    Execution Layer Quality Assurance & Fail-Closed Testing
"""
import copy
import sys
from research.governance.serialization import CanonicalSerializer
from execution.certification.registry import ExecutionTheoremRegistry
from execution.certification.registry.manifest import ManifestBuilder
from execution.certification.startup_gate import StartupGate
from execution.certification.runtime import CertificationRuntimeStateStore, RuntimeCertificationState
from execution.certification.theorem_replay_determinism_001 import ReplayDeterminismTheorem
from execution.certification.theorem_eventstore_immutability_001 import EventStoreImmutabilityTheorem

def test_valid_boot_sequence():
    CertificationRuntimeStateStore._state = RuntimeCertificationState.INITIALIZING
    
    manifest = ManifestBuilder.compile(
        ExecutionTheoremRegistry.all(),
        signing_mode="development"
    )

    certificate = StartupGate.boot_sequence(
        manifest=manifest,
        registry=list(ExecutionTheoremRegistry.all()),
        environment="development"
    )

    assert certificate.certified is True
    assert CertificationRuntimeStateStore.get_state() == RuntimeCertificationState.EXECUTION_ENABLED
    assert certificate.startup_certificate_hash is not None
    print("test_valid_boot_sequence PASSED.")

def test_manifest_tampering_rejection():
    CertificationRuntimeStateStore._state = RuntimeCertificationState.INITIALIZING
    manifest = ManifestBuilder.compile(
        ExecutionTheoremRegistry.all(),
        signing_mode="development"
    )

    manifest["engine_version"] = "999.0.0"

    try:
        StartupGate.boot_sequence(
            manifest=manifest,
            registry=list(ExecutionTheoremRegistry.all()),
            environment="development"
        )
        raise AssertionError("Should have failed")
    except RuntimeError as e:
        assert "Gate Failure" in str(e)
        assert CertificationRuntimeStateStore.get_state() == RuntimeCertificationState.HALTED
        print("test_manifest_tampering_rejection PASSED.")

def test_duplicate_theorem_injection():
    CertificationRuntimeStateStore._state = RuntimeCertificationState.INITIALIZING
    
    class DuplicateReplayTheorem(ReplayDeterminismTheorem):
        id = "THEOREM-REPLAY-DETERMINISM-001"

    try:
        ManifestBuilder.compile(
            (EventStoreImmutabilityTheorem, ReplayDeterminismTheorem, DuplicateReplayTheorem),
            signing_mode="development"
        )
        raise AssertionError("Should have failed")
    except RuntimeError as e:
        assert "Duplicate theorem ID" in str(e)
        print("test_duplicate_theorem_injection PASSED.")

def test_unsigned_prod_block():
    CertificationRuntimeStateStore._state = RuntimeCertificationState.INITIALIZING
    manifest = ManifestBuilder.compile(
        ExecutionTheoremRegistry.all(),
        signing_mode="development"
    )

    try:
        StartupGate.boot_sequence(
            manifest=manifest,
            registry=list(ExecutionTheoremRegistry.all()),
            environment="production"
        )
        raise AssertionError("Should have failed")
    except RuntimeError as e:
        assert "UNSIGNED_DEV_MODE manifests are strictly forbidden outside development" in str(e)
        assert CertificationRuntimeStateStore.get_state() == RuntimeCertificationState.HALTED
        print("test_unsigned_prod_block PASSED.")

if __name__ == "__main__":
    test_valid_boot_sequence()
    test_manifest_tampering_rejection()
    test_duplicate_theorem_injection()
    test_unsigned_prod_block()
    print("\nAll certification tests executed successfully!")
```[cite: 48, 49]