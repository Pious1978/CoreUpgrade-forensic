import copy
import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from src.security.crypto import StrictCryptographicEngine
from src.security.pki import RootPKIAuthority
from src.runtime.monitor import RuntimeIntegrityMonitor

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    failure_code: Optional[str] = None
    reason: Optional[str] = None
    theorem_bytecode_hashes: Optional[Dict[str, str]] = None

class RegistryValidator:
    @staticmethod
    def validate(manifest: Dict[str, Any], expected_env_hash: str, loaded_theorems: List[Any]) -> ValidationResult:
        manifest_clean = copy.deepcopy(manifest)
        
        manifest_clean.pop("registry_hash", None)
        manifest_clean.pop("signature", None)
        manifest_clean.pop("signature_metadata", None)
        manifest_clean.pop("certificate_signature", None)
        
        canonical_bytes = StrictCryptographicEngine.canonical_serialize(manifest_clean)
        recomputed_hash = hashlib.sha256(canonical_bytes).hexdigest()
        expected_hash = manifest.get("registry_hash")
        
        if recomputed_hash != expected_hash:
            return ValidationResult(
                valid=False,
                failure_code="MANIFEST_HASH_MISMATCH",
                reason="Recomputed canonical manifest digest does not match registry_hash."
            )
        
        sig_meta = manifest.get("signature_metadata", {})
        signature = sig_meta.get("signature") or manifest.get("signature")
        public_key = sig_meta.get("public_key")
        
        if not public_key or not signature:
            return ValidationResult(
                valid=False,
                failure_code="MISSING_SIGNATURE_CREDENTIALS",
                reason="Manifest lacks cryptographic public_key or signature."
            )

        if not StrictCryptographicEngine.verify_ed25519(public_key, signature, expected_hash.encode("utf-8")):
            return ValidationResult(
                valid=False,
                failure_code="INVALID_SIGNATURE",
                reason="Ed25519 cryptographic signature verification failed against registry hash."
            )

        if not RootPKIAuthority.verify_certificate_chain(manifest):
            return ValidationResult(
                valid=False,
                failure_code="PKI_CHAIN_VERIFICATION_FAILED",
                reason="Certificate trust chain validation against Root PKI Authority failed."
            )
        
        manifest_env_hash = manifest.get("environment_fingerprint")
        if manifest_env_hash and manifest_env_hash != expected_env_hash:
            return ValidationResult(
                valid=False,
                failure_code="ENVIRONMENT_FINGERPRINT_MISMATCH",
                reason=f"Environment fingerprint mismatch: expected {manifest_env_hash}, got {expected_env_hash}."
            )

        declared_theorems = manifest.get("theorems", [])
        theorem_lookup = {getattr(t, "id", None): t for t in loaded_theorems}

        if len(declared_theorems) != len(loaded_theorems):
            return ValidationResult(
                valid=False,
                failure_code="THEOREM_COUNT_MISMATCH",
                reason=f"Manifest declares {len(declared_theorems)} theorems, but {len(loaded_theorems)} were provided."
            )

        computed_bytecode_hashes = {}
        for t_def in declared_theorems:
            t_id = t_def.get("id")
            if not t_id or t_id not in theorem_lookup:
                return ValidationResult(
                    valid=False,
                    failure_code="INVALID_THEOREM_REGISTRY",
                    reason=f"Theorem ID '{t_id}' declared in manifest is missing from loaded runtime theorems."
                )
            
            theorem_obj = theorem_lookup[t_id]
            
            try:
                recomputed_bytecode_hash = RuntimeIntegrityMonitor.compute_bytecode_hash(theorem_obj)
            except Exception as e:
                return ValidationResult(
                    valid=False,
                    failure_code="THEOREM_BYTECODE_INSPECTION_FAILED",
                    reason=f"Failed to inspect compiled bytecode for theorem '{t_id}': {str(e)}"
                )

            declared_impl_hash = t_def.get("implementation_hash")
            if declared_impl_hash and declared_impl_hash != recomputed_bytecode_hash:
                return ValidationResult(
                    valid=False,
                    failure_code="THEOREM_BYTECODE_TAMPERED",
                    reason=f"Theorem '{t_id}' compiled bytecode hash mismatch! Declared: {declared_impl_hash}, Recomputed: {recomputed_bytecode_hash}."
                )

            computed_bytecode_hashes[t_id] = recomputed_bytecode_hash
        
        return ValidationResult(valid=True, theorem_bytecode_hashes=computed_bytecode_hashes)