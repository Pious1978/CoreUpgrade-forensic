import hashlib
import json
from typing import Any, Dict

class FingerprintEngine:
    """Handles deterministic cryptographic fingerprinting for governance artifacts and policies."""

    @staticmethod
    def generate_hash(payload: Dict[str, Any]) -> str:
        """
        Generates a deterministic SHA-256 hash for a given dictionary payload
        by sorting keys and standardizing encoding.
        """
        canonical = json.dumps(
            payload,
            sort_keys=True,
            default=str
        ).encode("utf-8")

        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def verify_fingerprint(payload: Dict[str, Any], expected_hash: str) -> bool:
        """Verifies if a given payload matches an expected cryptographic fingerprint."""
        current_hash = FingerprintEngine.generate_hash(payload)
        return current_hash == expected_hash
