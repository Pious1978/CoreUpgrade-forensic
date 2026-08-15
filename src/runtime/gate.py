import time
import threading
from typing import Dict, List, Any
from src.runtime.state import RuntimeStateController, RuntimeCertificationState
from src.runtime.persistent_counter import PersistentBootCounter
from src.validators.registry import RegistryValidator
from src.security.fingerprint import EnvironmentFingerprint
from src.execution.resolver import DependencyResolver
from src.execution.executor import TheoremExecutor, ExecutionSuiteResult
from src.security.issuer import CertificateIssuer
from src.security.certificate import StartupCertificate

class StartupGate:
    _boot_mutex = threading.Lock()

    @classmethod
    def boot_sequence(
        cls, 
        manifest: Dict[str, Any], 
        theorems: List[Any], 
        signing_mode: str = "PRODUCTION"
    ) -> StartupCertificate:
        with cls._boot_mutex:
            gate_timings: Dict[str, float] = {}
            t_start = time.perf_counter()
            gate_timings["boot_initiated"] = t_start

            current_boot_counter = PersistentBootCounter.get_and_increment()

            current_state = RuntimeStateController.get_state()
            if current_state in {RuntimeCertificationState.INITIALIZING, RuntimeCertificationState.EXECUTION_ENABLED}:
                RuntimeStateController.transition(RuntimeCertificationState.VALIDATING)
            else:
                RuntimeStateController.transition(RuntimeCertificationState.VALIDATING)

            try:
                env_fp = EnvironmentFingerprint()
                env_hash = env_fp.compute_hash()

                t_val_start = time.perf_counter()
                val_res = RegistryValidator.validate(manifest, env_hash, theorems)
                gate_timings["manifest_validation_duration"] = time.perf_counter() - t_val_start

                if not val_res.valid:
                    raise RuntimeError(f"Manifest validation failed [{val_res.failure_code}]: {val_res.reason}")

                t_dag_start = time.perf_counter()
                sorted_theorems, dag_hash = DependencyResolver.resolve_topological_sort(theorems)
                gate_timings["dependency_resolution_duration"] = time.perf_counter() - t_dag_start

                RuntimeStateController.transition(RuntimeCertificationState.CERTIFIED)

                t_exec_start = time.perf_counter()
                suite_result: ExecutionSuiteResult = TheoremExecutor.execute_suite(sorted_theorems)
                gate_timings["theorem_execution_duration"] = time.perf_counter() - t_exec_start

                if suite_result.failed:
                    raise RuntimeError(f"Theorem execution suite failed: {suite_result.diagnostics}")

                empirical_proof_hash = suite_result.proof_payload["empirical_proof_hash"]

                cert = CertificateIssuer.issue(
                    manifest=manifest,
                    env_hash=env_hash,
                    gate_timings=gate_timings,
                    signing_mode=signing_mode,
                    dependency_graph_hash=dag_hash,
                    empirical_proof_hash=empirical_proof_hash,
                    boot_counter=current_boot_counter,
                    theorem_bytecode_hashes=val_res.theorem_bytecode_hashes or {}
                )

                RuntimeStateController.set_active_certificate(cert)

                RuntimeStateController.transition(RuntimeCertificationState.EXECUTION_ENABLED)
                return cert

            except Exception as e:
                try:
                    RuntimeStateController.revoke_and_halt(str(e), fatal=True)
                except RuntimeError:
                    RuntimeStateController.force_halt(fatal=True)
                
                raise RuntimeError(f"StartupGate sequence aborted safely due to error: {str(e)}") from e