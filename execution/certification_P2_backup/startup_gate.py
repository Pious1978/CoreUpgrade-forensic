"""
Startup Gate Boot Coordinator

Authority:
    Execution Layer Boot Sequencing & Modular Pipeline Coordination
"""
import time
from typing import List, Type, Optional, Any
from research.governance.serialization import CanonicalSerializer
from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.engine.registry_validator import RegistryValidator
from execution.certification.engine.dependency_resolver import DependencyResolver
from execution.certification.engine.theorem_executor import TheoremExecutor
from execution.certification.engine.proof_builder import ProofBuilder
from execution.certification.engine.certificate_issuer import StartupCertificate, CertificateIssuer
from execution.certification.engine.runtime_state_controller import RuntimeStateController, RuntimeCertificationState

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except ImportError:
    Ed25519PublicKey = None

class StartupGate:
    @staticmethod
    def verify_signature(registry_hash_hex: str, signature_hex: str, public_key_bytes: Optional[bytes] = None, environment: str = "production") -> bool:
        if signature_hex == "UNSIGNED_DEV_MODE":
            if environment != "development":
                raise RuntimeError("CRITICAL: UNSIGNED_DEV_MODE forbidden outside development.")
            return True

        if public_key_bytes is None or Ed25519PublicKey is None:
            return False

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            pub_key.verify(bytes.fromhex(signature_hex), bytes.fromhex(registry_hash_hex))
            return True
        except Exception:
            return False

    @classmethod
    def boot_sequence(
        cls,
        *,
        manifest: Any,
        registry: List[Type[EmpiricalTheorem]],
        environment: str = "production",
        public_key: Optional[bytes] = None
    ) -> StartupCertificate:
        print("\n================================================")
        print(" EXECUTION ENGINE BOOT CERTIFICATION")
        print("================================================")
        
        gate_timings = {}
        RuntimeStateController.transition(RuntimeCertificationState.VALIDATING)

        try:
            manifest_dict = manifest.to_dict()

            t0 = time.perf_counter()
            if manifest_dict.get("engine_version") != EXECUTION_ENGINE_VERSION:
                raise RuntimeError("Engine version mismatch.")
            gate_timings["engine_version_ms"] = (time.perf_counter() - t0) * 1000
            print("[1] Manifest Compilation\n        OK\n        Registry Hash:\n        " + manifest_dict.get("registry_hash", "")[:12] + "...")

            t0 = time.perf_counter()
            current_env = CanonicalSerializer.get_environment_fingerprint()
            stored_env = manifest_dict.get("environment_fingerprint", {})
            
            critical_keys = ["python_version", "os", "serializer_version"]
            for ck in critical_keys:
                if stored_env.get(ck) != current_env.get(ck):
                    raise RuntimeError(f"Critical environment drift on '{ck}'. Expected {stored_env.get(ck)}, got {current_env.get(ck)}")
            gate_timings["environment_check_ms"] = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            if not cls.verify_signature(manifest_dict.get("registry_hash"), manifest_dict.get("signature"), public_key, environment=environment):
                raise RuntimeError("Registry cryptographic signature verification failed.")
            gate_timings["signature_verify_ms"] = (time.perf_counter() - t0) * 1000
            print("\n[2] Cryptographic Validation\n        OK\n        Signature:\n        " + manifest_dict.get("signature_mode", "ED25519"))

            t0 = time.perf_counter()
            validation_res = RegistryValidator.validate(registry, manifest)
            if not validation_res.valid:
                raise RuntimeError(f"Registry validation failed [{validation_res.failure_code}]: {validation_res.reason}")
            gate_timings["registry_integrity_ms"] = (time.perf_counter() - t0) * 1000
            print("\n[3] Registry Integrity\n        OK\n        Theorems:\n        " + str(manifest_dict.get("registry_size")))

            t0 = time.perf_counter()
            sorted_theorems, dag_hash = DependencyResolver.resolve_topological_sort(registry)
            gate_timings["dependency_dag_ms"] = (time.perf_counter() - t0) * 1000
            print("\n[4] Dependency Graph\n        OK\n        DAG Verified (Hash: " + dag_hash[:12] + "...)")

            t0 = time.perf_counter()
            results, _, execution_order, _, failed = TheoremExecutor.execute_suite(sorted_theorems, EXECUTION_ENGINE_VERSION)
            if failed > 0:
                raise RuntimeError(f"Empirical theorem execution failed: {failed} uncertified.")
            
            registry_payload = {
                "schema_version": manifest_dict.get("schema_version", "1.0"),
                "manifest_hash": manifest_dict.get("registry_hash"),
                "registered_theorems": [{"id": t.id, "version": t.version} for t in sorted_theorems]
            }
            registry_fingerprint = CanonicalSerializer.digest(registry_payload)

            master_proof_hash, _, _ = ProofBuilder.build_proof(
                master_id="THEOREM-EXECUTION-EMPIRICAL-001",
                master_version="13.0.0",
                engine_version=EXECUTION_ENGINE_VERSION,
                schema_version="1.0",
                proof_schema="1.0",
                hash_algorithm="SHA-256",
                all_certified=True,
                registry_manifest_hash=manifest_dict.get("registry_hash"),
                registry_fingerprint=registry_fingerprint,
                dependency_graph_hash=dag_hash,
                sorted_theorems=sorted_theorems,
                results=results,
                execution_order=execution_order
            )
            gate_timings["empirical_tests_ms"] = (time.perf_counter() - t0) * 1000
            print("\n[5] Empirical Certification\n        PASS\n        Proof Hash:\n        " + master_proof_hash[:12] + "...")

            RuntimeStateController.transition(RuntimeCertificationState.CERTIFIED)
            print("\n[6] Runtime State Lock\n        CERTIFIED")

            env_hash = CanonicalSerializer.digest(current_env)
            certificate = CertificateIssuer.issue(
                manifest=manifest,
                env_hash=env_hash,
                gate_timings=gate_timings,
                empirical_proof_hash=master_proof_hash,
                total_theorems=len(sorted_theorems),
                signing_mode=manifest_dict.get("signature_mode", "ED25519")
            )

            if not CertificateIssuer.verify(certificate, public_key, environment=environment):
                raise RuntimeError("Certificate cryptographic verification failed.")

            RuntimeStateController.set_active_certificate(certificate)
            RuntimeStateController.transition(RuntimeCertificationState.EXECUTION_ENABLED)
            certificate.persist()

            print("\n[7] Execution Gate\n        OPEN")
            print("================================================")
            print(" TRADING EXECUTION AUTHORIZED")
            print("================================================\n")

            return certificate

        except Exception as e:
            RuntimeStateController.transition(RuntimeCertificationState.HALTED)
            print(f"\nCRITICAL: Startup gate breached or failed. Engine transitioned to HALTED. Reason: {e}")
            raise
