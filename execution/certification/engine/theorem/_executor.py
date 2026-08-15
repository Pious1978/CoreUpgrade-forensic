from __future__ import annotations

"""
Theorem Executor Engine

Authority:
Execution Certification Theorem Execution & Dependency Governance
"""

import time
import traceback
from types import MappingProxyType
from typing import Any, Dict, List, Tuple, Type

from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.results.empirical_result import ExecutionResult


class TheoremExecutor:
    """
    Executes the ordered empirical theorem suite.

    Responsibilities:
    - Dependency gating
    - Engine-version compatibility
    - Theorem execution
    - ExecutionResult normalization
    - Failure taxonomy normalization
    - Runtime diagnostics isolation
    - Deterministic execution ordering
    - Proof-field filtering
    """

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
        engine_version: str,
    ) -> Tuple[
        Dict[str, Any],
        Dict[str, Any],
        List[str],
        int,
        int,
    ]:
        results: Dict[str, Any] = {}
        diagnostics: Dict[str, Any] = {}
        execution_order: List[str] = []

        passed = 0
        failed = 0

        theorem_status: Dict[str, Dict[str, Any]] = {}

        for theorem in sorted_theorems:
            theorem_id = theorem.id
            execution_order.append(theorem_id)

            sub_start = time.perf_counter()
            sub_res: Dict[str, Any] = {}

            # -----------------------------------------------------
            # 1. Dependency gating
            # -----------------------------------------------------
            blocked_by_dependency = False
            blocked_reason = None

            deps = getattr(theorem, "depends_on", ())

            for dep_id in deps:
                dep_info = theorem_status.get(dep_id)

                if dep_info is None:
                    blocked_by_dependency = True
                    blocked_reason = (
                        f"Blocked: prerequisite dependency "
                        f"'{dep_id}' has not been executed."
                    )
                    break

                if not dep_info.get("certified", False):
                    dep_severity = dep_info.get(
                        "severity",
                        "ERROR",
                    )

                    action = cls.DEPENDENCY_SEVERITY_POLICY.get(
                        dep_severity,
                        "BLOCK",
                    )

                    if action == "BLOCK":
                        blocked_by_dependency = True
                        blocked_reason = (
                            f"Blocked: prerequisite dependency "
                            f"'{dep_id}' failed with "
                            f"{dep_severity} severity."
                        )
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

            # -----------------------------------------------------
            # 2. Engine-version compatibility
            # -----------------------------------------------------
            elif not theorem.supports(engine_version):
                sub_res = {
                    "certified": False,
                    "failure_type": "version_incompatibility",
                    "failure_origin": "CONFIGURATION",
                    "severity": "FATAL",
                    "reason_code": "ENGINE_VERSION_MISMATCH",
                    "reason": (
                        f"Theorem requires engine version >= "
                        f"{getattr(theorem, 'required_engine_version', 'unknown')} "
                        f"but orchestrator is running "
                        f"{engine_version}."
                    ),
                }

            # -----------------------------------------------------
            # 3. Execute theorem
            # -----------------------------------------------------
            else:
                try:
                    raw_result = theorem.verify()

                    # -------------------------------------------------
                    # 3A. Strongly typed ExecutionResult
                    # -------------------------------------------------
                    if isinstance(raw_result, ExecutionResult):
                        sub_res = {
                            "certified": raw_result.certified,
                            "failure_origin": raw_result.failure_origin,
                            "failure_type": raw_result.failure_type,
                            "severity": raw_result.severity,
                            "reason_code": raw_result.reason_code,
                            "diagnostics": dict(
                                raw_result.diagnostics
                            ),
                            "evidence": dict(
                                raw_result.evidence
                            ),
                            "proof": dict(
                                raw_result.proof
                            ),
                        }

                    # -------------------------------------------------
                    # 3B. Dictionary theorem result
                    # -------------------------------------------------
                    elif isinstance(raw_result, dict):
                        sub_res = dict(raw_result)

                        is_certified = bool(
                            sub_res.get(
                                "certified",
                                False,
                            )
                        )

                        sub_res.setdefault(
                            "failure_type",
                            (
                                None
                                if is_certified
                                else "proof_failure"
                            ),
                        )

                        sub_res.setdefault(
                            "failure_origin",
                            (
                                None
                                if is_certified
                                else "THEOREM"
                            ),
                        )

                        sub_res.setdefault(
                            "severity",
                            (
                                "INFO"
                                if is_certified
                                else getattr(
                                    theorem,
                                    "severity",
                                    "ERROR",
                                )
                            ),
                        )

                        sub_res.setdefault(
                            "reason_code",
                            (
                                "SUCCESS"
                                if is_certified
                                else "PROOF_ASSERTION_FAILED"
                            ),
                        )

                    # -------------------------------------------------
                    # 3C. Invalid theorem response
                    # -------------------------------------------------
                    else:
                        sub_res = {
                            "certified": False,
                            "failure_type": "invalid_response",
                            "failure_origin": "THEOREM",
                            "severity": getattr(
                                theorem,
                                "severity",
                                "ERROR",
                            ),
                            "reason_code": "INVALID_RETURN_FORMAT",
                            "reason": (
                                "Theorem returned unsupported "
                                "response type: "
                                f"{type(raw_result).__name__}."
                            ),
                        }

                except Exception as exc:
                    tb = traceback.format_exc()

                    sub_res = {
                        "certified": False,
                        "failure_type": "exception",
                        "failure_origin": "RUNTIME",
                        "severity": getattr(
                            theorem,
                            "severity",
                            "FATAL",
                        ),
                        "reason_code": "UNHANDLED_EXCEPTION",
                        "exception_type": type(exc).__name__,
                        "reason": str(exc),
                    }

                    diagnostics[theorem_id] = {
                        "traceback": tb,
                        "exception_type": type(exc).__name__,
                    }

            # -----------------------------------------------------
            # 4. Execution timing
            # -----------------------------------------------------
            sub_end = time.perf_counter()

            execution_ms = round(
                (sub_end - sub_start) * 1000,
                3,
            )

            diagnostics.setdefault(
                theorem_id,
                {},
            )["execution_ms"] = execution_ms

            # -----------------------------------------------------
            # 5. Normalize theorem status
            # -----------------------------------------------------
            theorem_status[theorem_id] = {
                "certified": bool(
                    sub_res.get(
                        "certified",
                        False,
                    )
                ),
                "severity": sub_res.get(
                    "severity",
                    "ERROR",
                ),
            }

            # -----------------------------------------------------
            # 6. Build proof record
            # -----------------------------------------------------
            allowed_fields = getattr(
                theorem,
                "ALLOWED_PROOF_FIELDS",
                EmpiricalTheorem.ALLOWED_PROOF_FIELDS,
            )

            proof_data = {
                key: value
                for key, value in sub_res.items()
                if key in allowed_fields
            }

            proof_data.setdefault(
                "certified",
                sub_res.get(
                    "certified",
                    False,
                ),
            )

            proof_data.setdefault(
                "failure_type",
                sub_res.get(
                    "failure_type",
                ),
            )

            proof_data.setdefault(
                "failure_origin",
                sub_res.get(
                    "failure_origin",
                ),
            )

            proof_data.setdefault(
                "severity",
                sub_res.get(
                    "severity",
                    "ERROR",
                ),
            )

            proof_data.setdefault(
                "reason_code",
                sub_res.get(
                    "reason_code",
                    "UNKNOWN",
                ),
            )

            # -----------------------------------------------------
            # 7. Store theorem result
            # -----------------------------------------------------
            results[theorem_id] = {
                "proof": proof_data,
                "metadata": {
                    "theorem_version": theorem.version,
                    "proof_schema": "1.0",
                    "authority": getattr(
                        theorem,
                        "authority",
                        "Unknown",
                    ),
                    "domain": getattr(
                        theorem,
                        "domain",
                        "Unknown",
                    ),
                },
            }

            # -----------------------------------------------------
            # 8. Aggregate pass/fail counts
            # -----------------------------------------------------
            if sub_res.get(
                "certified",
                False,
            ):
                passed += 1
            else:
                failed += 1

        # ---------------------------------------------------------
        # 9. Freeze diagnostics
        # ---------------------------------------------------------
        frozen_diagnostics = MappingProxyType(
            {
                key: MappingProxyType(value)
                if isinstance(value, dict)
                else value
                for key, value in diagnostics.items()
            }
        )

        return (
            results,
            frozen_diagnostics,
            execution_order,
            passed,
            failed,
        )
