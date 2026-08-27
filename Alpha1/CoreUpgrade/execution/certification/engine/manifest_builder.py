"""
Manifest Builder & Asymmetric Ed25519 Signing Engine

Authority:
    Execution Layer Governance Manifest Compilation & Cryptographic Signing
"""
import inspect
import copy
import textwrap
from types import MappingProxyType
from typing import Tuple, Type, Dict, Any, List, Optional
from research.governance.serialization import CanonicalSerializer
from execution.manifest import EXECUTION_ENGINE_VERSION
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None

def deep_freeze(obj: Any) -> Any:
    if isinstance(obj, MappingProxyType):
        return obj
    if isinstance(obj, dict):
        return MappingProxyType({str(k): deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, frozenset):
        return frozenset(deep_freeze(x) for x in obj)
    if isinstance(obj, set):
        return frozenset(deep_freeze(x) for x in obj)
    if isinstance(obj, (list, tuple)):
        return tuple(deep_freeze(x) for x in obj)
    return obj

class ImmutableManifest:
    def __init__(self, data: Dict[str, Any]):
        self._frozen_data = deep_freeze(data)

    def __getitem__(self, key: str) -> Any:
        return self._frozen_data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._frozen_data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        def unfreeze(val: Any) -> Any:
            if isinstance(val, MappingProxyType):
                return {k: unfreeze(v) for k, v in val.items()}
            if isinstance(val, (tuple, frozenset)):
                return [unfreeze(x) for x in val]
            return val
        return unfreeze(self._frozen_data)


class ManifestBuilder:
    @staticmethod
    def normalize_bytecode_and_constants(t: Type[EmpiricalTheorem]) -> str:
        code_bytes = b""
        constants = []
        if hasattr(t, "verify"):
            if hasattr(t.verify, "__code__"):
                code_bytes = t.verify.__code__.co_code
                constants = [str(c) for c in t.verify.__code__.co_consts]

        payload = {
            "bytecode": code_bytes.hex(),
            "constants": constants,
            "name": t.__name__,
            "module": t.__module__
        }
        return CanonicalSerializer.hash(payload)

    @classmethod
    def compile(
        cls, 
        registered_classes: Tuple[Type[EmpiricalTheorem], ...], 
        signing_mode: str = "ED25519",
        private_key_bytes: Optional[bytes] = None
    ) -> ImmutableManifest:
        seen_ids = set()
        theorems_manifest = []

        for t in sorted(registered_classes, key=lambda x: x.id):
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

            impl_hash = cls.normalize_bytecode_and_constants(t)

            theorems_manifest.append({
                "id": theorem_id,
                "module": t.__module__,
                "class": t.__name__,
                "version": version,
                "authority": authority,
                "domain": domain,
                "depends_on": depends_on,
                "implementation_hash": impl_hash,
            })
        
        environment_fingerprint = {
            "schema": "1.0",
            **CanonicalSerializer.get_environment_fingerprint()
        }

        structural_manifest = {
            "manifest_id": "EXECUTION-THEOREM-REGISTRY",
            "schema_version": "1.0",
            "engine_version": EXECUTION_ENGINE_VERSION,
            "serializer_version": "1.0.0",
            "hash_algorithm": "SHA-256",
            "registry_size": len(registered_classes),
            "signature_mode": signing_mode,
            "environment_fingerprint": environment_fingerprint,
            "theorems": theorems_manifest,
        }
        
        registry_hash = CanonicalSerializer.digest(structural_manifest)

        if signing_mode == "development":
            signature = "UNSIGNED_DEV_MODE"
        else:
            if Ed25519PrivateKey is None or private_key_bytes is None:
                raise RuntimeError("Ed25519 private key required for production signing.")
            priv_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            signature_bytes = priv_key.sign(bytes.fromhex(registry_hash))
            signature = signature_bytes.hex()

        final_manifest = {
            **structural_manifest,
            "registry_hash": registry_hash,
            "signature": signature
        }

        return ImmutableManifest(final_manifest)
```[cite: 32]