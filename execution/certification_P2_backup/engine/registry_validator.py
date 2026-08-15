"""
Registry Validator Engine with Structured Diagnostics

Authority:
    Execution Layer Theorem Identity and Source Integrity Verification
"""
import inspect
from dataclasses import dataclass
from typing import List, Type, Optional, Any
from research.governance.serialization import CanonicalSerializer
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

@dataclass(frozen=True)
class RegistryValidationResult:
    valid: bool
    failure_code: Optional[str] = None
    theorem_id: Optional[str] = None
    reason: Optional[str] = None

class RegistryValidator:
    @staticmethod
    def validate(registered_classes: List[Type[EmpiricalTheorem]], manifest: Any) -> RegistryValidationResult:
        manifest_dict = manifest.to_dict()
        
        if len(registered_classes) != manifest_dict.get("registry_size", -1):
            return RegistryValidationResult(
                valid=False, 
                failure_code="REGISTRY_SIZE_MISMATCH", 
                reason=f"Expected {manifest_dict.get('registry_size')} theorems, got {len(registered_classes)}"
            )

        manifest_map = {x["id"]: x for x in manifest_dict.get("theorems", [])}
        seen_ids = set()

        for theorem in registered_classes:
            t_id = getattr(theorem, "id", None)
            if not t_id or t_id in seen_ids:
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="DUPLICATE_OR_MISSING_ID", 
                    theorem_id=t_id, 
                    reason=f"Theorem {theorem.__name__} has duplicate or missing ID."
                )
            seen_ids.add(t_id)

            if t_id not in manifest_map:
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="UNREGISTERED_THEOREM", 
                    theorem_id=t_id, 
                    reason=f"Theorem {t_id} not found in manifest map."
                )

            expected = manifest_map[t_id]
            
            if theorem.__module__ != expected.get("module") or theorem.__name__ != expected.get("class"):
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="CLASS_LOCATION_DRIFT", 
                    theorem_id=t_id, 
                    reason=f"Class location mismatch for {t_id}."
                )
            
            if theorem.version != expected.get("version"):
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="VERSION_MISMATCH", 
                    theorem_id=t_id, 
                    reason=f"Version mismatch for {t_id}."
                )
            
            if not getattr(theorem, "authority", None):
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="MISSING_AUTHORITY", 
                    theorem_id=t_id, 
                    reason=f"Theorem {t_id} missing authority metadata."
                )

            code_bytes = b""
            constants = []
            if hasattr(theorem, "verify"):
                if hasattr(theorem.verify, "__code__"):
                    code_bytes = theorem.verify.__code__.co_code
                    constants = [str(c) for c in theorem.verify.__code__.co_consts]

            actual_signature = {
                "bytecode": code_bytes.hex(),
                "constants": constants,
                "name": theorem.__name__,
                "module": theorem.__module__
            }
            if CanonicalSerializer.hash(actual_signature) != expected.get("implementation_hash"):
                return RegistryValidationResult(
                    valid=False, 
                    failure_code="IMPLEMENTATION_HASH_MISMATCH", 
                    theorem_id=t_id, 
                    reason=f"Implementation bytecode hash mismatch for {t_id}. Code logic modified."
                )

        return RegistryValidationResult(valid=True)
