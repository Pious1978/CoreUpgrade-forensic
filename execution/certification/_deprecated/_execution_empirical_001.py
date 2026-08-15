"""
THEOREM-EXECUTION-EMPIRICAL-001

Master Execution Certification Orchestrator

Authority:
Execution Layer Certification Governance

Purpose:
    Provides the master empirical certification contract for the
    execution layer.

Architectural rule:
    This theorem does NOT discover the registry itself.

    Registry ownership belongs exclusively to:

        execution.certification.registry

    Execution ownership belongs to:

        execution.certification.engine.theorem._executor

    Dependency resolution belongs to:

        execution.certification.engine.dependency._resolver

    Cryptographic proof construction belongs to:

        execution.certification.engine.proof._builder

This theorem therefore acts as the master certification identity and
result/proof aggregation contract rather than creating a second,
competing theorem-execution pipeline.
"""

import inspect
import time
import traceback

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Type

from research.governance.serialization import CanonicalSerializer

from execution.manifest import EXECUTION_ENGINE_VERSION

from execution.certification.contracts.empirical_theorem import (
    EmpiricalTheorem,
)

from execution.certification.results.empirical_result import (
    ExecutionResult,
    ExecutionEmpiricalResult,
)


class ExecutionEmpiricalTheorem(EmpiricalTheorem):
    """
    Master empirical certification theorem.

    This class represents:

        THEOREM-EXECUTION-EMPIRICAL-001

    It aggregates already-validated theorem executions into a single
    immutable empirical certification result.

    It deliberately does not perform registry discovery.

    The canonical execution path is:

        Registry
            ↓
        RegistryValidator
            ↓
        DependencyResolver
            ↓
        TheoremExecutor
            ↓
        ExecutionEmpiricalTheorem
            ↓
        ProofBuilder
            ↓
        CertificateIssuer
    """

    # ------------------------------------------------------------------
    # MASTER THEOREM IDENTITY
    # ------------------------------------------------------------------

    id = "THEOREM-EXECUTION-EMPIRICAL-001"

    version = "13.0.0"

    required_engine_version = EXECUTION_ENGINE_VERSION
    engine_version = EXECUTION_ENGINE_VERSION

    schema_version = "1.0"
    proof_schema = "1.0"
    registry_schema_version = "1.0"
    hash_algorithm = "SHA-256"

    authority = "Execution Certification Governance"
    domain = "Execution Layer Master Empirical Certification"

    created_at = "2026-08-01"
    deprecated = False

    # ------------------------------------------------------------------
    # DEPENDENCY POLICY
    # ------------------------------------------------------------------

    DEPENDENCY_POLICY = {
        "BLOCK_FATAL": True,
        "BLOCK_ERROR": False,
    }

    # ------------------------------------------------------------------
    # REGISTRY VALIDATION
    # ------------------------------------------------------------------

    @classmethod
    def validate_registry_explicit(
        cls,
        available_classes: List[Type[EmpiricalTheorem]],
    ) -> Tuple[Type[EmpiricalTheorem], ...]:
        """
        Validate an explicitly supplied theorem collection.

        IMPORTANT:
            This method does not discover theorem classes.

        The caller must provide the canonical registry contents.

        Validation includes:

            1. class type
            2. EmpiricalTheorem inheritance
            3. abstract-class rejection
            4. theorem ID
            5. theorem version
            6. authority metadata
            7. callable verify()
            8. duplicate theorem IDs
            9. dependency existence
            10. dependency cycle detection
            11. deterministic topological ordering
        """

        if available_classes is None:
            raise TypeError(
                "available_classes cannot be None."
            )

        validated_map: Dict[
            str,
            Type[EmpiricalTheorem]
        ] = {}

        seen_ids = set()

        # --------------------------------------------------------------
        # Validate theorem classes
        # --------------------------------------------------------------

        for theorem in available_classes:

            if (
                not isinstance(theorem, type)
                or not issubclass(theorem, EmpiricalTheorem)
            ):
                raise TypeError(
                    f"Registered theorem {theorem!r} "
                    "does not subclass EmpiricalTheorem."
                )

            if inspect.isabstract(theorem):
                raise TypeError(
                    f"Registered theorem {theorem.__name__} "
                    "is abstract and cannot be executed."
                )

            theorem_id = getattr(theorem, "id", None)
            theorem_version = getattr(theorem, "version", None)
            authority = getattr(theorem, "authority", None)

            if not theorem_id:
                raise ValueError(
                    f"Theorem {theorem.__name__} "
                    "lacks mandatory 'id' metadata."
                )

            if not theorem_version:
                raise ValueError(
                    f"Theorem {theorem.__name__} "
                    "lacks mandatory 'version' metadata."
                )

            if not authority:
                raise RuntimeError(
                    f"Theorem {theorem_id} "
                    "missing mandatory authority metadata."
                )

            if theorem_id in seen_ids:
                raise RuntimeError(
                    f"Duplicate theorem ID detected: "
                    f"'{theorem_id}'."
                )

            verify_method = getattr(theorem, "verify", None)

            if not callable(verify_method):
                raise TypeError(
                    f"Theorem {theorem.__name__} "
                    "'verify' attribute is not callable."
                )

            seen_ids.add(theorem_id)
            validated_map[theorem_id] = theorem

        # --------------------------------------------------------------
        # Deterministic dependency topological sort
        # --------------------------------------------------------------

        sorted_theorems: List[
            Type[EmpiricalTheorem]
        ] = []

        visited = set()
        temp_marked = set()

        def visit(theorem_id: str) -> None:

            if theorem_id in temp_marked:
                raise RuntimeError(
                    "Circular dependency detected involving "
                    f"theorem '{theorem_id}'."
                )

            if theorem_id in visited:
                return

            temp_marked.add(theorem_id)

            theorem_cls = validated_map[theorem_id]

            dependencies = tuple(
                sorted(
                    getattr(
                        theorem_cls,
                        "depends_on",
                        (),
                    )
                )
            )

            for dependency_id in dependencies:

                if dependency_id not in validated_map:
                    raise KeyError(
                        f"Theorem '{theorem_id}' depends on "
                        f"unregistered theorem "
                        f"'{dependency_id}'."
                    )

                visit(dependency_id)

            temp_marked.remove(theorem_id)
            visited.add(theorem_id)

            sorted_theorems.append(theorem_cls)

        for theorem_id in sorted(validated_map.keys()):
            visit(theorem_id)

        return tuple(sorted_theorems)

    # ------------------------------------------------------------------
    # RESULT NORMALIZATION
    # ------------------------------------------------------------------

    @classmethod
    def _normalize_result(
        cls,
        theorem: Type[EmpiricalTheorem],
        result: Any,
    ) -> Dict[str, Any]:
        """
        Normalize either a dict or ExecutionResult into the canonical
        proof dictionary consumed by the master certification layer.
        """

        if isinstance(result, ExecutionResult):

            normalized = {
                "certified": result.certified,
                "failure_origin": result.failure_origin,
                "failure_type": result.failure_type,
                "severity": result.severity,
                "reason_code": result.reason_code,
                "diagnostics": result.diagnostics,
                "evidence": result.evidence,
                "proof": result.proof,
            }

        elif isinstance(result, dict):

            normalized = dict(result)

        else:

            normalized = {
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
                    "Theorem returned unsupported result "
                    f"type: {type(result).__name__}"
                ),
            }

        certified = bool(
            normalized.get("certified", False)
        )

        normalized.setdefault(
            "failure_type",
            None if certified else "proof_failure",
        )

        normalized.setdefault(
            "failure_origin",
            None if certified else "THEOREM",
        )

        normalized.setdefault(
            "severity",
            "INFO" if certified else getattr(
                theorem,
                "severity",
                "ERROR",
            ),
        )

        normalized.setdefault(
            "reason_code",
            "SUCCESS" if certified else "PROOF_ASSERTION_FAILED",
        )

        return normalized

    # ------------------------------------------------------------------
    # MASTER VERIFICATION
    # ------------------------------------------------------------------

    @classmethod
    def verify_with_registry(
        cls,
        sorted_theorems: Tuple[
            Type[EmpiricalTheorem],
            ...
        ],
        registry_manifest_hash: str,
        registry_fingerprint: str,
    ) -> ExecutionEmpiricalResult:
        """
        Execute an explicitly supplied and already ordered theorem set.

        This method exists for compatibility with the master empirical
        certification contract.

        The startup gate / TheoremExecutor remains the canonical runtime
        execution mechanism.

        No registry discovery occurs here.
        """

        if not isinstance(sorted_theorems, tuple):
            sorted_theorems = tuple(sorted_theorems)

        start_time = time.perf_counter()

        execution_timestamp = (
            datetime.now(timezone.utc).isoformat()
        )

        results: Dict[str, Dict[str, Any]] = {}
        diagnostics: Dict[str, Dict[str, Any]] = {}
        execution_order: List[str] = []

        passed = 0
        failed = 0

        theorem_status: Dict[
            str,
            Dict[str, Any]
        ] = {}

        expected_self_proof = {
            "theorem_id": cls.id,
            "version": cls.version,
            "proof_schema": cls.proof_schema,
            "registry_schema_version": (
                cls.registry_schema_version
            ),
            "registry_fingerprint": registry_fingerprint,
            "registry_manifest_hash": registry_manifest_hash,
            "engine_version": cls.engine_version,
            "hash_algorithm": cls.hash_algorithm,
        }

        # --------------------------------------------------------------
        # Execute theorem collection
        # --------------------------------------------------------------

        for theorem in sorted_theorems:

            theorem_id = theorem.id
            theorem_version = theorem.version

            execution_order.append(theorem_id)

            sub_start = time.perf_counter()

            blocked_by_dependency = False
            blocked_reason = None

            dependencies = tuple(
                getattr(
                    theorem,
                    "depends_on",
                    (),
                )
            )

            # ----------------------------------------------------------
            # Dependency admission
            # ----------------------------------------------------------

            for dependency_id in dependencies:

                dependency_info = theorem_status.get(
                    dependency_id,
                    {},
                )

                dependency_certified = dependency_info.get(
                    "certified",
                    True,
                )

                if dependency_certified:
                    continue

                dependency_severity = dependency_info.get(
                    "severity",
                    "ERROR",
                )

                if (
                    cls.DEPENDENCY_POLICY["BLOCK_FATAL"]
                    and dependency_severity == "FATAL"
                ):
                    blocked_by_dependency = True

                    blocked_reason = (
                        "Blocked: prerequisite dependency "
                        f"'{dependency_id}' failed with "
                        "FATAL severity."
                    )

                    break

                if (
                    cls.DEPENDENCY_POLICY["BLOCK_ERROR"]
                    and dependency_severity
                    in ("FATAL", "ERROR")
                ):
                    blocked_by_dependency = True

                    blocked_reason = (
                        "Blocked: prerequisite dependency "
                        f"'{dependency_id}' failed with "
                        f"{dependency_severity} severity."
                    )

                    break

            # ----------------------------------------------------------
            # Execute theorem
            # ----------------------------------------------------------

            if blocked_by_dependency:

                sub_result = {
                    "certified": False,
                    "failure_type": "dependency_blocked",
                    "failure_origin": "DEPENDENCY",
                    "severity": "FATAL",
                    "reason_code": "PREREQUISITE_FAILURE",
                    "reason": blocked_reason,
                }

            elif not theorem.supports(cls.engine_version):

                sub_result = {
                    "certified": False,
                    "failure_type": "version_incompatibility",
                    "failure_origin": "CONFIGURATION",
                    "severity": "FATAL",
                    "reason_code": "ENGINE_VERSION_MISMATCH",
                    "reason": (
                        "Theorem requires engine version >= "
                        f"{getattr(theorem, 'required_engine_version', 'unknown')} "
                        "but orchestrator is running "
                        f"{cls.engine_version}."
                    ),
                }

            else:

                try:

                    verify_method = getattr(
                        theorem,
                        "verify",
                    )

                    sub_result = verify_method()

                    sub_result = cls._normalize_result(
                        theorem,
                        sub_result,
                    )

                except Exception as exc:

                    diagnostics[theorem_id] = {
                        "traceback": traceback.format_exc(),
                        "exception_type": type(exc).__name__,
                    }

                    sub_result = {
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

            # ----------------------------------------------------------
            # Timing
            # ----------------------------------------------------------

            sub_end = time.perf_counter()

            execution_ms = round(
                (sub_end - sub_start) * 1000,
                3,
            )

            diagnostics.setdefault(
                theorem_id,
                {}
            )["execution_ms"] = execution_ms

            # ----------------------------------------------------------
            # Status
            # ----------------------------------------------------------

            theorem_status[theorem_id] = {
                "certified": bool(
                    sub_result.get(
                        "certified",
                        False,
                    )
                ),
                "severity": sub_result.get(
                    "severity",
                    "ERROR",
                ),
            }

            # ----------------------------------------------------------
            # Proof field filtering
            # ----------------------------------------------------------

            allowed_fields = getattr(
                theorem,
                "ALLOWED_PROOF_FIELDS",
                cls.ALLOWED_PROOF_FIELDS,
            )

            proof_data = {
                key: value
                for key, value in sub_result.items()
                if key in allowed_fields
            }

            proof_data.setdefault(
                "certified",
                sub_result.get(
                    "certified",
                    False,
                ),
            )

            proof_data.setdefault(
                "failure_type",
                sub_result.get(
                    "failure_type"
                ),
            )

            proof_data.setdefault(
                "failure_origin",
                sub_result.get(
                    "failure_origin"
                ),
            )

            proof_data.setdefault(
                "severity",
                sub_result.get(
                    "severity",
                    "ERROR",
                ),
            )

            proof_data.setdefault(
                "reason_code",
                sub_result.get(
                    "reason_code",
                    "UNKNOWN",
                ),
            )

            # ----------------------------------------------------------
            # Master result record
            # ----------------------------------------------------------

            results[theorem_id] = {
                "proof": proof_data,
                "metadata": {
                    "theorem_version": theorem_version,
                    "proof_schema": cls.proof_schema,
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

            if sub_result.get(
                "certified",
                False,
            ):
                passed += 1
            else:
                failed += 1

        # --------------------------------------------------------------
        # Master certification state
        # --------------------------------------------------------------

        duration_ms = round(
            (
                time.perf_counter()
                - start_time
            ) * 1000,
            3,
        )

        all_certified = failed == 0

        reason = (
            None
            if all_certified
            else (
                "Execution empirical validation failed: "
                f"{failed} sub-theorem(s) uncertified."
            )
        )

        # --------------------------------------------------------------
        # Environment provenance
        # --------------------------------------------------------------

        environment_fingerprint = (
            CanonicalSerializer
            .get_environment_fingerprint()
        )

        provenance = {
            "git_commit": "HEAD",
            "engine_manifest_hash": (
                CanonicalSerializer.digest(
                    {
                        "version": cls.engine_version
                    }
                )
            ),
            "registry_manifest_hash": (
                registry_manifest_hash
            ),
            "registry_fingerprint": (
                registry_fingerprint
            ),
            "environment": (
                environment_fingerprint
            ),
            "serializer_version": "1.0.0",
        }

        # --------------------------------------------------------------
        # Deterministic master proof payload
        # --------------------------------------------------------------

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
            "results": {
                key: results[key]
                for key in sorted(results.keys())
            },
        }

        master_proof_hash = (
            CanonicalSerializer.digest(
                proof_payload
            )
        )

        # --------------------------------------------------------------
        # Immutable master result
        # --------------------------------------------------------------

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