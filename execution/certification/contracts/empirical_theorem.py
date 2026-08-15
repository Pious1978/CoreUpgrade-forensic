"""
Empirical Theorem Base Contract

Authority:
Execution Layer Certification

Purpose:
Defines the canonical interface and governance metadata contract
for all decentralized empirical execution certification theorems.
"""

from abc import ABC, abstractmethod
from typing import Tuple

from packaging.version import Version

from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.results.empirical_result import ExecutionResult


class EmpiricalTheorem(ABC):
    """
    Standardized abstract base class enforcing a strict interface contract
    for all decentralized empirical execution theorems.

    The contract governs:

    - theorem identity
    - semantic version compatibility
    - dependency declaration
    - failure severity
    - institutional audit lineage
    - proof-field whitelisting
    - theorem verification interface
    """

    # ------------------------------------------------------------------
    # THEOREM IDENTITY
    # ------------------------------------------------------------------

    id: str
    version: str

    # ------------------------------------------------------------------
    # ENGINE COMPATIBILITY
    # ------------------------------------------------------------------

    required_engine_version: str = EXECUTION_ENGINE_VERSION

    # ------------------------------------------------------------------
    # DEPENDENCY GOVERNANCE
    # ------------------------------------------------------------------

    depends_on: Tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # FAILURE SEVERITY
    #
    # INFO     -> informational theorem result
    # WARNING  -> non-blocking warning
    # ERROR    -> certification failure
    # FATAL    -> certification/security failure
    # ------------------------------------------------------------------

    severity: str = "ERROR"

    # ------------------------------------------------------------------
    # INSTITUTIONAL AUDIT LINEAGE
    # ------------------------------------------------------------------

    authority: str = "Execution Governance"
    domain: str = "Order Lifecycle & Event Sourcing"
    created_at: str = "2026-08-01"
    deprecated: bool = False

    # ------------------------------------------------------------------
    # PROOF SCHEMA GOVERNANCE
    #
    # Only these fields are permitted to cross the theorem -> proof
    # boundary.
    # ------------------------------------------------------------------

    ALLOWED_PROOF_FIELDS = {
        "certified",
        "failure_type",
        "failure_origin",
        "severity",
        "rule",
        "reason_code",
        "evidence",
        "proofs",
    }

    # ------------------------------------------------------------------
    # ENGINE VERSION COMPATIBILITY
    # ------------------------------------------------------------------

    @classmethod
    def supports(cls, engine_version: str) -> bool:
        """
        Verify semantic compatibility between the theorem and the
        currently running execution engine.

        Compatibility rules:

        1. The theorem's required engine version must be valid.
        2. The running engine version must be valid.
        3. Both versions must have the same major version.
        4. The running engine version must be greater than or equal to
           the theorem's required version.

        Returns:
            True  -> theorem is compatible with the running engine.
            False -> theorem is incompatible or version parsing failed.
        """

        try:
            required = Version(cls.required_engine_version)
            running = Version(engine_version)

            return (
                required.major == running.major
                and running >= required
            )

        except Exception:
            return False

    # ------------------------------------------------------------------
    # THEOREM EXECUTION CONTRACT
    # ------------------------------------------------------------------

    @classmethod
    @abstractmethod
    def verify(cls, *args, **kwargs) -> dict | ExecutionResult:
        """
        Execute the theorem's empirical certification logic.

        Implementations must return either:

            dict
                A structured theorem proof/result payload.

        or:

            ExecutionResult
                A standardized execution result object.

        The executor is responsible for normalizing the result,
        enforcing proof-field restrictions, recording diagnostics,
        and determining certification status.
        """
        raise NotImplementedError(
            f"{cls.__name__}.verify() must implement the empirical "
            "certification contract."
        )