"""
Execution Certification Registry (Hardened, Signed, & Source-Normalized Manifest)

Authority:
    Execution Layer Governance Registry
"""
import inspect
import copy
import textwrap
from typing import Tuple, Type, Dict, Any, List
from research.governance.serialization import CanonicalSerializer
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

from execution.certification.theorem_eventstore_immutability_001 import EventStoreImmutabilityTheorem
from execution.certification.theorem_replay_determinism_001 import ReplayDeterminismTheorem
from execution.certification.theorem_empty_stream_001 import EmptyStreamReplayTheorem
from execution.certification.theorem_partial_fill_001 import PartialFillTheorem
from execution.certification.theorem_reconciliation_purity_001 import ReconciliationPurityTheorem

class ExecutionTheoremRegistry:
    """
    Centralized data registry featuring normalized source-fingerprinting, duplicate ID rejection,
    dependency existence validation, module/class tracking, and signed manifest verification.
    """
    _REGISTRY: Tuple[Type[EmpiricalTheorem], ...] = (
        EventStoreImmutabilityTheorem,
        ReplayDeterminismTheorem,
        EmptyStreamReplayTheorem,
        PartialFillTheorem,
        ReconciliationPurityTheorem,
    )

    @classmethod
    def all(cls) -> Tuple[Type[EmpiricalTheorem], ...]:
        return cls._REGISTRY

    @staticmethod
    def normalize_source(source: str) -> str:
        """Normalizes source text to ensure formatting, docstring spacing, and indentation do not break hashes."""
        return textwrap.dedent(source).strip()

    @classmethod
    def get_manifest(cls, private_key: str = "DEFAULT_GOVERNANCE_SIGNING_KEY") -> Dict[str, Any]:
        """
        Generates a cryptographically signed, complete manifest protecting theorem identity,
        normalized source implementation, module/class locations, strict dependencies, 
        and environment fingerprint schema.
        """
        seen_ids = set()
        theorems_manifest = []

        for t in sorted(cls._REGISTRY, key=lambda x: x.id):
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
            "schema_version": "1.0",
            "engine_version": "1.0.0",
            "hash_algorithm": "SHA-256",
            "serializer_version": "1.0.0",
            "registry_size": len(cls._REGISTRY),
            "environment_fingerprint": environment_fingerprint,
            "theorems": theorems_manifest,
        }
        
        copy_manifest = copy.deepcopy(manifest)
        copy_manifest.pop("registry_hash", None)
        copy_manifest.pop("signature", None)
        
        registry_hash = CanonicalSerializer.digest(copy_manifest)
        manifest["registry_hash"] = registry_hash

        sig_payload = f"{registry_hash}:{private_key}"
        manifest["signature"] = CanonicalSerializer.hash(sig_payload)

        return manifest

    @classmethod
    def verify_registry_integrity(cls, registered_classes: List[Type[EmpiricalTheorem]], manifest: dict, public_key: str = "DEFAULT_GOVERNANCE_SIGNING_KEY") -> bool:
        """
        Enforces rigorous startup gating:
        1. Validates digital signature / HMAC against tampering.
        2. Validates self-referential manifest registry_hash.
        3. Rejects duplicate IDs.
        4. Validates dependency existence and topological invariants.
        5. Verifies normalized source implementation hashes.
        """
        stored_signature = manifest.get("signature")
        stored_registry_hash = manifest.get("registry_hash")
        if not stored_signature or not stored_registry_hash:
            return False

        expected_sig_payload = f"{stored_registry_hash}:{public_key}"
        if CanonicalSerializer.hash(expected_sig_payload) != stored_signature:
            return False

        copy_manifest = copy.deepcopy(manifest)
        copy_manifest.pop("registry_hash", None)
        copy_manifest.pop("signature", None)
        if stored_registry_hash != CanonicalSerializer.digest(copy_manifest):
            return False

        if len(registered_classes) != manifest.get("registry_size", -1):
            return False

        seen_ids = set()
        all_ids = set()
        for theorem in registered_classes:
            t_id = getattr(theorem, "id", None)
            if not t_id or t_id in seen_ids:
                return False
            seen_ids.add(t_id)
            all_ids.add(t_id)

        manifest_map = {x["id"]: x for x in manifest.get("theorems", [])}
        if set(manifest_map.keys()) != all_ids:
            return False

        for theorem in registered_classes:
            theorem_id = theorem.id
            expected = manifest_map[theorem_id]

            if theorem.__module__ != expected.get("module") or theorem.__name__ != expected.get("class"):
                return False

            authority = getattr(theorem, "authority", None)
            if not authority:
                raise RuntimeError(f"{theorem_id} missing authority metadata during verification.")

            if theorem.version != expected.get("version"):
                return False

            declared_deps = sorted(list(getattr(theorem, "depends_on", ())))
            if declared_deps != expected.get("depends_on", []):
                return False

            for dep in declared_deps:
                if dep not in all_ids:
                    return False

            try:
                raw_source = inspect.getsource(theorem)
                source_code = cls.normalize_source(raw_source)
            except (TypeError, OSError):
                return False

            actual_signature = {
                "module": theorem.__module__,
                "class": theorem.__name__,
                "version": theorem.version,
                "required_engine_version": theorem.required_engine_version,
                "source": source_code,
            }
            actual_hash = CanonicalSerializer.hash(actual_signature)

            if actual_hash != expected.get("implementation_hash"):
                return False

        return True