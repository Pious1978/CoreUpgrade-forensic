"""
Theorem Executor Engine

Authority:
    Execution Certification Theorem Execution & Dependency Governance
"""
import time
import traceback
from typing import Dict, Any, Tuple, Type, List
from types import MappingProxyType
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

class TheoremExecutor:
    DEPENDENCY_SEVERITY_POLICY = {
        "INFO": "ALLOW",
        "WARNING": "ALLOW",
        "ERROR": "BLOCK",
        "FATAL": "BLOCK",
    }

    @classmethod
    def execute_suite(
        cls, 
        sorted_theorems: Tuple[Type[EmpiricalTheorem], ...], 
        engine_version: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], int, int]:
        results = {}
        diagnostics = {}
        execution_order = []
        passed = 0
        failed = 0
        theorem_status: Dict[str, Dict[str, Any]] = {}

        for theorem in sorted_theorems:
            theorem_id = theorem.id
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
                    action = cls.DEPENDENCY_SEVERITY_POLICY.get(dep_severity, "BLOCK")
                    if action == "BLOCK":
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
            elif not theorem.supports(engine_version):
                sub_res = {
                    "certified": False,
                    "failure_type": "version_incompatibility",
                    "failure_origin": "CONFIGURATION",
                    "severity": "FATAL",
                    "reason_code": "ENGINE_VERSION_MISMATCH",
                    "reason": f"Theorem requires engine version >= {getattr(theorem, 'required_engine_version', 'unknown')} but orchestrator is running {engine_version}.",
                }
            else:
                try:
                    sub_res = theorem.verify()

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

            allowed_fields = getattr(theorem, "ALLOWED_PROOF_FIELDS", EmpiricalTheorem.ALLOWED_PROOF_FIELDS)
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
                    "proof_schema": "1.0",
                    "authority": getattr(theorem, "authority", "Unknown"),
                    "domain": getattr(theorem, "domain", "Unknown"),
                }
            }

            if sub_res.get("certified", False):
                passed += 1
            else:
                failed += 1

        frozen_diagnostics = MappingProxyType({
            k: MappingProxyType(v) if isinstance(v, dict) else v
            for k, v in diagnostics.items()
        })

        return results, frozen_diagnostics, execution_order, passed, failed
```[cite: 19]