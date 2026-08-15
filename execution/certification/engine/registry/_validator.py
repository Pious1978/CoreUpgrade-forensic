"""
Registry Validator Engine with Structured Diagnostics

Authority:
    Execution Layer Theorem Identity and Implementation Integrity Verification
"""

from dataclasses import dataclass
from typing import List, Type, Optional, Any

from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.certification.engine.manifest._builder import ManifestBuilder


@dataclass(frozen=True)
class RegistryValidationResult:
    valid: bool
    failure_code: Optional[str] = None
    theorem_id: Optional[str] = None
    reason: Optional[str] = None


class RegistryValidator:

    @staticmethod
    def validate(
        registered_classes: List[Type[EmpiricalTheorem]],
        manifest: Any,
    ) -> RegistryValidationResult:

        manifest_dict = manifest

        # ------------------------------------------------------------
        # 1. Registry size integrity
        # ------------------------------------------------------------
        if len(registered_classes) != manifest_dict.get("registry_size", -1):
            return RegistryValidationResult(
                valid=False,
                failure_code="REGISTRY_SIZE_MISMATCH",
                reason=(
                    f"Expected {manifest_dict.get('registry_size')} "
                    f"theorems, got {len(registered_classes)}"
                ),
            )

        manifest_map = {
            x["id"]: x
            for x in manifest_dict.get("theorems", [])
        }

        seen_ids = set()

        # ------------------------------------------------------------
        # 2. Validate every registered theorem
        # ------------------------------------------------------------
        for theorem in registered_classes:

            t_id = getattr(theorem, "id", None)

            # --------------------------------------------------------
            # Theorem identity
            # --------------------------------------------------------
            if not t_id or t_id in seen_ids:
                return RegistryValidationResult(
                    valid=False,
                    failure_code="DUPLICATE_OR_MISSING_ID",
                    theorem_id=t_id,
                    reason=(
                        f"Theorem {theorem.__name__} has "
                        "duplicate or missing ID."
                    ),
                )

            seen_ids.add(t_id)

            # --------------------------------------------------------
            # Registration presence
            # --------------------------------------------------------
            if t_id not in manifest_map:
                return RegistryValidationResult(
                    valid=False,
                    failure_code="UNREGISTERED_THEOREM",
                    theorem_id=t_id,
                    reason=(
                        f"Theorem {t_id} not found in manifest map."
                    ),
                )

            expected = manifest_map[t_id]

            # --------------------------------------------------------
            # Class/module identity
            # --------------------------------------------------------
            if (
                theorem.__module__ != expected.get("module")
                or theorem.__name__ != expected.get("class")
            ):
                return RegistryValidationResult(
                    valid=False,
                    failure_code="CLASS_LOCATION_DRIFT",
                    theorem_id=t_id,
                    reason=(
                        f"Class location mismatch for {t_id}."
                    ),
                )

            # --------------------------------------------------------
            # Version integrity
            # --------------------------------------------------------
            if theorem.version != expected.get("version"):
                return RegistryValidationResult(
                    valid=False,
                    failure_code="VERSION_MISMATCH",
                    theorem_id=t_id,
                    reason=(
                        f"Version mismatch for {t_id}."
                    ),
                )

            # --------------------------------------------------------
            # Authority metadata
            # --------------------------------------------------------
            if not getattr(theorem, "authority", None):
                return RegistryValidationResult(
                    valid=False,
                    failure_code="MISSING_AUTHORITY",
                    theorem_id=t_id,
                    reason=(
                        f"Theorem {t_id} missing authority metadata."
                    ),
                )

            # --------------------------------------------------------
            # Implementation integrity
            #
            # IMPORTANT:
            # ManifestBuilder creates implementation_hash using:
            #
            #     normalize_bytecode_and_constants()
            #
            # The validator MUST use the exact same canonical
            # implementation-hashing algorithm.
            # --------------------------------------------------------
            try:
                actual_implementation_hash = (
                    ManifestBuilder.normalize_bytecode_and_constants(
                        theorem
                    )
                )

            except Exception as exc:
                return RegistryValidationResult(
                    valid=False,
                    failure_code="IMPLEMENTATION_HASH_FAILED",
                    theorem_id=t_id,
                    reason=(
                        f"Failed to calculate implementation "
                        f"integrity hash for {t_id}: {exc}"
                    ),
                )

            expected_implementation_hash = expected.get(
                "implementation_hash"
            )

            if (
                actual_implementation_hash
                != expected_implementation_hash
            ):
                return RegistryValidationResult(
                    valid=False,
                    failure_code="IMPLEMENTATION_HASH_MISMATCH",
                    theorem_id=t_id,
                    reason=(
                        f"Implementation integrity hash mismatch "
                        f"for {t_id}. Code logic modified."
                    ),
                )

        # ------------------------------------------------------------
        # All registry checks passed
        # ------------------------------------------------------------
        return RegistryValidationResult(valid=True)
