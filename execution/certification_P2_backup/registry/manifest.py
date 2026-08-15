"""
Manifest Builder & Signing Engine

Authority:
    Execution Layer Governance Manifest Compilation
"""

import copy
import inspect
import textwrap
from typing import Any, Dict, Tuple, Type

from research.governance.serialization import CanonicalSerializer
from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
from execution.manifest import EXECUTION_ENGINE_VERSION


class ManifestBuilder:
    """Compile registered empirical theorems into a canonical manifest."""

    @staticmethod
    def normalize_source(source: str) -> str:
        """Normalize source code before hashing."""
        return textwrap.dedent(source).strip()

    @staticmethod
    def _validate_theorem_class(theorem_class: Type[EmpiricalTheorem]) -> None:
        """Validate mandatory theorem metadata."""
        theorem_id = getattr(theorem_class, "id", None)

        if not theorem_id:
            raise RuntimeError(
                f"Theorem class {theorem_class.__name__} "
                "missing required unique 'id'."
            )

        authority = getattr(theorem_class, "authority", None)

        if not authority:
            raise RuntimeError(
                f"Theorem {theorem_id} missing mandatory 'authority' metadata."
            )

        if not hasattr(theorem_class, "required_engine_version"):
            raise RuntimeError(
                f"Theorem {theorem_id} missing required "
                "'required_engine_version' metadata."
            )

    @classmethod
    def _build_theorem_manifest(
        cls,
        theorem_class: Type[EmpiricalTheorem],
    ) -> Dict[str, Any]:
        """Build the canonical manifest entry for one theorem."""

        cls._validate_theorem_class(theorem_class)

        theorem_id = theorem_class.id
        version = getattr(theorem_class, "version", "1.0.0")
        authority = theorem_class.authority
        domain = getattr(theorem_class, "domain", "General")
        depends_on = sorted(
            list(getattr(theorem_class, "depends_on", ()))
        )

        try:
            raw_source = inspect.getsource(theorem_class)
        except (TypeError, OSError) as exc:
            raise RuntimeError(
                f"Failed to extract source for {theorem_id}: {exc}"
            ) from exc

        source_code = cls.normalize_source(raw_source)

        implementation_payload = {
            "module": theorem_class.__module__,
            "class": theorem_class.__name__,
            "version": version,
            "required_engine_version": (
                theorem_class.required_engine_version
            ),
            "source": source_code,
        }

        implementation_hash = CanonicalSerializer.hash(
            implementation_payload
        )

        return {
            "id": theorem_id,
            "module": theorem_class.__module__,
            "class": theorem_class.__name__,
            "version": version,
            "required_engine_version": (
                theorem_class.required_engine_version
            ),
            "authority": authority,
            "domain": domain,
            "depends_on": depends_on,
            "implementation_hash": implementation_hash,
        }

    @staticmethod
    def _sign_registry_hash(
        registry_hash: str,
        private_key: Any,
    ) -> str:
        """
        Create an Ed25519 signature over the registry hash.

        Accepted private key formats:
            - 32-byte Ed25519 private seed
            - 64-character hexadecimal seed
        """

        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError as exc:
            raise RuntimeError(
                "cryptography is required for production manifest signing."
            ) from exc

        if private_key is None:
            raise RuntimeError(
                "Production manifest signing requires an Ed25519 private key."
            )

        if isinstance(private_key, str):
            private_key = private_key.strip()

            if len(private_key) == 64:
                try:
                    private_key = bytes.fromhex(private_key)
                except ValueError as exc:
                    raise RuntimeError(
                        "private_key must be a valid 64-character "
                        "hexadecimal Ed25519 seed."
                    ) from exc
            else:
                raise RuntimeError(
                    "private_key must be supplied as a 32-byte value "
                    "or 64-character hexadecimal Ed25519 seed."
                )

        if not isinstance(private_key, bytes):
            raise RuntimeError(
                "private_key must be bytes or a hexadecimal string."
            )

        if len(private_key) != 32:
            raise RuntimeError(
                "Ed25519 private key must contain exactly 32 bytes."
            )

        signing_key = Ed25519PrivateKey.from_private_bytes(private_key)

        registry_hash_bytes = bytes.fromhex(registry_hash)

        signature = signing_key.sign(registry_hash_bytes)

        return signature.hex()

    @classmethod
    def compile(
        cls,
        registered_classes: Tuple[Type[EmpiricalTheorem], ...],
        signing_mode: str = "production",
        private_key: Any = None,
    ) -> Dict[str, Any]:
        """
        Compile registered theorems into a cryptographically bound manifest.

        Development mode:
            signature = UNSIGNED_DEV_MODE

        Production mode:
            manifest is signed using Ed25519.
        """

        if signing_mode not in {"development", "production"}:
            raise RuntimeError(
                "Invalid signing_mode. Expected 'development' "
                "or 'production'."
            )

        seen_ids = set()
        theorems_manifest = []

        sorted_classes = sorted(
            registered_classes,
            key=lambda theorem_class: theorem_class.id,
        )

        for theorem_class in sorted_classes:
            theorem_id = getattr(theorem_class, "id", None)

            if theorem_id in seen_ids:
                raise RuntimeError(
                    "Duplicate theorem ID detected during manifest "
                    f"compilation: '{theorem_id}'."
                )

            seen_ids.add(theorem_id)

            theorem_manifest = cls._build_theorem_manifest(
                theorem_class
            )

            theorems_manifest.append(theorem_manifest)

        environment_fingerprint = {
            "schema": "1.0",
            **CanonicalSerializer.get_environment_fingerprint(),
        }

        manifest = {
            "manifest_id": "EXECUTION-THEOREM-REGISTRY",
            "manifest_schema": "1.0",
            "engine_version": EXECUTION_ENGINE_VERSION,
            "serializer_version": "1.0.0",
            "hash_algorithm": "SHA-256",
            "registry_size": len(theorems_manifest),
            "signature_mode": (
                "UNSIGNED_DEV_MODE"
                if signing_mode == "development"
                else "ED25519"
            ),
            "environment_fingerprint": environment_fingerprint,
            "theorems": theorems_manifest,
        }

        # Hash only the unsigned canonical manifest.
        unsigned_manifest = copy.deepcopy(manifest)

        registry_hash = CanonicalSerializer.digest(
            unsigned_manifest
        )

        manifest["registry_hash"] = registry_hash

        if signing_mode == "development":
            manifest["signature"] = "UNSIGNED_DEV_MODE"
        else:
            manifest["signature"] = cls._sign_registry_hash(
                registry_hash,
                private_key,
            )

        return manifest