"""
THEOREM-EXECUTION-EMPIRICAL-001 (Master Orchestrator)

Institutional governance orchestrator for the execution layer.
Aggregates decentralized empirical sub-theorems into a unified cryptographic proof,
accepting explicit pre-validated theorem collections.
"""
import time
import traceback
import inspect
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Type, List
from types import MappingProxyType

from research.governance.serialization import CanonicalSerializer
from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.results.empirical_result import ExecutionEmpiricalResult


class ExecutionEmpiricalTheorem(EmpiricalTheorem):
    """
    Master empirical certification orchestrator supporting explicit registry input.
    """
    id = "THEOREM-EXECUTION-EMPIRICAL-001"
    version = "12.0.0"
    required_engine_version = EXECUTION_ENGINE_VERSION
    engine_version = EXECUTION_ENGINE_VERSION
    schema_version = "1.0"
    proof_schema = "1.0"
    registry_schema_version = "1.0"
    hash_algorithm = "SHA-256"

    DEPENDENCY_POLICY = {
        "BLOCK_FATAL": True,
        "BLOCK_ERROR": False,
    }

    @classmethod
    def validate_registry_explicit(cls, available_classes: List[Type[EmpiricalTheorem]]) -> Tuple[Type[EmpiricalTheorem], ...]:
        """
        Validates an explicitly provided theorem collection.
        Enforces subclass adherence, abstract class checks, unique theorem IDs, 
        authority metadata, and resolves the topological dependency graph.
        """
        validated_map = {}
        seen_ids = set()

        for theorem in available_classes:
            if not isinstance(theorem, type) or not issubclass(theorem, EmpiricalTheorem):
                raise TypeError(f"Registered theorem {theorem} does not subclass EmpiricalTheorem.")
            if inspect.isabstract(theorem):
                raise TypeError(f"Registered theorem {theorem} is an abstract class and cannot be executed.")
            
            theorem_id = getattr(theorem, "id", None)
            theorem_version = getattr(theorem, "version", None)
            authority = getattr(theorem, "authority", None)

            if not theorem_id or not theorem_version:
                raise ValueError(f"Theorem {theorem.__name__} lacks mandatory 'id' or 'version' attributes.")
            
            if not authority:
                raise RuntimeError(f"Theorem {theorem_id} missing mandatory authority metadata.")
            
            if theorem_id in seen_ids:
                raise RuntimeError(f"Duplicate theorem ID detected: '{theorem_id}'.")
            
            verify_method = getattr(theorem, "verify", None)
            if not callable(verify_method):
                raise TypeError(f"Theorem {theorem.__name__} 'verify' attribute is not callable.")
            
            seen_ids.add(theorem_id)
            validated_map[theorem_id] = theorem

        # Topological sort based on depends_on graph
        sorted_theorems: List[Type[EmpiricalTheorem]] = []
        visited = set()
        temp_marked = set()

        def visit(t_id: str):
            if t_id in temp_marked:
                raise RuntimeError(f"Circular dependency detected involving theorem '{t_id}'.")
            if t_id not in visited:
                temp_marked.add(t_id)
                theorem_cls = validated_map[t_id]
                deps = getattr(theorem_cls, "depends_on", ())
                for dep_id in deps:
                    if dep_id not in validated_map:
                        raise KeyError(f"Theorem '{t_id}' depends on unregistered theorem '{dep_id}'.")
                    visit(dep_id)
                temp_marked.remove(t_id)
                visited.add(t_id)
                sorted_theorems.append(theorem_cls)

        for t_id in sorted(validated_map.keys()):
            if t_id not in visited:
                visit(t_id)

        return tuple(sorted_theorems)

    @classmethod
    def verify_with_registry(cls, sorted_theorems: Tuple[Type[EmpiricalTheorem], ...], registry_manifest_hash: str, registry_fingerprint: str) -> ExecutionEmpiricalResult:
        """
        Executes the master certification suite using an explicitly passed, validated theorem tuple.
        """
        start_time = time.perf_counter()
        execution_timestamp = datetime.now(timezone.utc).isoformat()
        
        results = {}
        diagnostics = {}
        execution_order = []
        passed = 0
        failed = 0
        theorem_status: Dict[str, Dict[str, Any]] = {}

        expected_self_proof = {
            "theorem_id": cls.id,
            "version": cls.version,
            "proof_schema": cls.proof_schema,
            "registry_schema_version": cls.registry_schema_version,
            "registry_fingerprint": registry_fingerprint,
            "registry_manifest_hash": registry_manifest_hash,
            "engine_version": cls.engine_version,
            "hash_algorithm": cls.hash_algorithm,
        }

        for theorem in sorted_theorems:
            theorem_id = theorem.id
            theorem_version = theorem.version
            execution_order.append(theorem_id)

            sub_start = time.perf_counter()
            sub_res = {}

            blocked_by_dependency = False
            blocked_reason = None
            deps = getattr(theorem, "depends_on", ())
            for dep_id in deps:
                dep_info = theorem_status.get(dep_id, {})
                if not dep_info.get("certified", True):
                    dep_severity = dep_info.get("severity", "ERROR")
                    if cls.DEPENDENCY_POLICY["BLOCK_FATAL"] and dep_severity == "FATAL":
                        blocked_by_dependency = True
                        blocked_reason = f"Blocked: prerequisite dependency '{dep_id}' failed with FATAL severity."
                        break
                    elif cls.DEPENDENCY_POLICY["BLOCK_ERROR"] and dep_severity in ("FATAL", "ERROR"):
                        blocked_by_dependency = True
                        blocked_reason = f"Blocked: prerequisite dependency '{dep_id}' failed with {dep_severity} severity."
                        break

            if blocked_by_dependency:
                sub_res = {
                    "certified": False,
                    "failure_type": "dependency_blocked",
                    "failure_origin": "DEPENDENCY",
                    "severity": "FATAL",
                    "reason_code": "PREREQUISITE_FAILURE",
                    "reason": blocked_reason,
                }
            elif not theorem.supports(cls.engine_version):
                sub_res = {
                    "certified": False,
                    "failure_type": "version_incompatibility",
                    "failure_origin": "CONFIGURATION",
                    "severity": "FATAL",
                    "reason_code": "ENGINE_VERSION_MISMATCH",
                    "reason": f"Theorem requires engine version >= {getattr(theorem, 'required_engine_version', 'unknown')} but orchestrator is running {cls.engine_version}.",
                }
            else:
                try:
                    if inspect.ismethod(theorem.verify) or isinstance(theorem.verify, classmethod):
                        sub_res = theorem.verify()
                    else:
                        instance = theorem()
                        sub_res = instance.verify()

                    if not isinstance(sub_res, dict):
                        sub_res = {
                            "certified": False,
                            "failure_type": "invalid_response",
                            "failure_origin": "THEOREM",
                            "severity": getattr(theorem, "severity", "ERROR"),
                            "reason_code": "INVALID_RETURN_FORMAT",
                            "reason": f"Theorem returned non-dict response structure: {sub_res!r}",
                        }
                    else:
                        is_cert = sub_res.get("certified", False)
                        sub_res.setdefault("failure_type", "proof_failure" if not is_cert else None)
                        sub_res.setdefault("failure_origin", "THEOREM" if not is_cert else None)
                        sub_res.setdefault("severity", getattr(theorem, "severity", "ERROR") if not is_cert else "INFO")
                        sub_res.setdefault("reason_code", "PROOF_ASSERTION_FAILED" if not is_cert else "SUCCESS")
                except Exception as exc:
                    tb = traceback.format_exc()
                    sub_res = {
                        "certified": False,
                        "failure_type": "exception",
                        "failure_origin": "RUNTIME",
                        "severity": getattr(theorem, "severity", "FATAL"),
                        "reason_code": "UNHANDLED_EXCEPTION",
                        "exception_type": type(exc).__name__,
                        "reason": str(exc),
                    }
                    diagnostics[theorem_id] = {
                        "traceback": tb,
                        "exception_type": type(exc).__name__
                    }
            
            sub_end = time.perf_counter()
            execution_ms = round((sub_end - sub_start) * 1000, 3)

            diagnostics.setdefault(theorem_id, {})["execution_ms"] = execution_ms

            theorem_status[theorem_id] = {
                "certified": sub_res.get("certified", False),
                "severity": sub_res.get("severity", "ERROR"),
            }

            allowed_fields = getattr(theorem, "ALLOWED_PROOF_FIELDS", cls.ALLOWED_PROOF_FIELDS)
            proof_data = {
                k: v for k, v in sub_res.items() if k in allowed_fields
            }
            proof_data.setdefault("certified", sub_res.get("certified", False))
            proof_data.setdefault("failure_type", sub_res.get("failure_type"))
            proof_data.setdefault("failure_origin", sub_res.get("failure_origin"))
            proof_data.setdefault("severity", sub_res.get("severity", "ERROR"))
            proof_data.setdefault("reason_code", sub_res.get("reason_code", "UNKNOWN"))

            results[theorem_id] = {
                "proof": proof_data,
                "metadata": {
                    "theorem_version": theorem.version,
                    "proof_schema": cls.proof_schema,
                    "authority": getattr(theorem, "authority", "Unknown"),
                    "domain": getattr(theorem, "domain", "Unknown"),
                }
            }
            
            if sub_res.get("certified", False):
                passed += 1
            else:
                failed += 1

        end_time = time.perf_counter()
        duration_ms = round((end_time - start_time) * 1000, 3)

        all_certified = (failed == 0)
        reason = None if all_certified else f"Execution empirical validation failed: {failed} sub-theorem(s) uncertified."

        environment_fingerprint = CanonicalSerializer.get_environment_fingerprint()

        provenance = {
            "git_commit": "HEAD",
            "engine_manifest_hash": CanonicalSerializer.digest({"version": cls.engine_version}),
            "registry_manifest_hash": registry_manifest_hash,
            "registry_fingerprint": registry_fingerprint,
            "environment": environment_fingerprint,
            "serializer_version": "1.0.0",
        }

        proof_payload = {
            "schema_version": cls.schema_version,
            "proof_schema": cls.proof_schema,
            "hash_algorithm": cls.hash_algorithm,
            "certified": all_certified,
            "theorem_id": cls.id,
            "version": cls.version,
            "engine_version": cls.engine_version,
            "registry_fingerprint": registry_fingerprint,
            "provenance": provenance,
            "orchestrator_self_proof": expected_self_proof,
            "results": results,
        }
        
        master_proof_hash = CanonicalSerializer.digest(proof_payload)

        return ExecutionEmpiricalResult(
            schema_version=cls.schema_version,
            proof_schema=cls.proof_schema,
            certified=all_certified,
            theorem_id=cls.id,
            theorem_version=cls.version,
            engine_version=cls.engine_version,
            execution_timestamp=execution_timestamp,
            total_theorems=len(sorted_theorems),
            passed=passed,
            failed=failed,
            execution_order=execution_order,
            registry_fingerprint=registry_fingerprint,
            provenance=provenance,
            results=results,
            diagnostics=diagnostics,
            master_proof_hash=master_proof_hash,
            duration_ms=duration_ms,
            reason=reason,
        )