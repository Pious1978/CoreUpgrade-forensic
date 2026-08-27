"""
Institutional PKI Verification Layer

Trust hierarchy:
ROOT CA -> INTERMEDIATE CA -> LEAF EXECUTION KEY -> STARTUP CERTIFICATE
"""

import os
from typing import Dict, Any

from src.security.crypto import StrictCryptographicEngine


class RootPKIAuthority:

    ROOT_CA_PATH = "/etc/trading-engine/trust/root_ca.der"
    
    INTERMEDIATE_PURPOSE = "TRADING_ENGINE_INTERMEDIATE_CA"
    LEAF_PURPOSE = "TRADING_ENGINE_EXECUTION_KEY"

    @classmethod
    def get_root_public_key(cls) -> bytes:
        if not os.path.isfile(cls.ROOT_CA_PATH):
            raise RuntimeError("CRITICAL SECURITY ERROR: Root CA missing.")

        try:
            with open(cls.ROOT_CA_PATH, "rb") as handle:
                public_key = handle.read()
        except OSError as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Unable to read Root CA: {exc}") from exc

        if not public_key:
            raise RuntimeError("CRITICAL SECURITY ERROR: Root CA is empty.")

        return public_key

    @classmethod
    def verify_intermediate_ca(cls, intermediate_cert: Dict[str, Any]) -> bytes:
        try:
            intermediate_key = bytes.fromhex(intermediate_cert["public_key_hex"])
            signature = bytes.fromhex(intermediate_cert["signature_hex"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("CRITICAL SECURITY ERROR: Invalid intermediate certificate encoding.") from exc

        # 1. Strict RFC8785 Serialization
        payload = StrictCryptographicEngine.rfc8785_canonical_serialize({
            "key_id": intermediate_cert.get("key_id"),
            "public_key_hex": intermediate_key.hex(),
            "generation": intermediate_cert.get("generation", 1),
            "purpose": cls.INTERMEDIATE_PURPOSE,
        })

        # 2. Single-path verification
        verified = StrictCryptographicEngine.verify_ecdsa_p384(
            public_key_der=cls.get_root_public_key(),
            signature=signature,
            message=payload,
            context="INTERMEDIATE_CA",
        )

        if not verified:
            raise RuntimeError("CRITICAL SECURITY ERROR: Intermediate CA signature invalid.")

        return intermediate_key

    @classmethod
    def verify_leaf_key(cls, leaf_public_key: bytes, intermediate_cert: Dict[str, Any]) -> bool:
        if not leaf_public_key:
            raise RuntimeError("CRITICAL SECURITY ERROR: Leaf public key missing.")

        intermediate_key = cls.verify_intermediate_ca(intermediate_cert)

        try:
            leaf_signature = bytes.fromhex(intermediate_cert["leaf_signature_hex"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("CRITICAL SECURITY ERROR: Leaf certificate signature missing or malformed.") from exc

        # 1. Strict RFC8785 Serialization
        payload = StrictCryptographicEngine.rfc8785_canonical_serialize({
            "public_key_hex": leaf_public_key.hex(),
            "authority_key_hex": intermediate_key.hex(),
            "purpose": cls.LEAF_PURPOSE,
        })

        # 2. Single-path verification
        return StrictCryptographicEngine.verify_ecdsa_p384(
            public_key_der=intermediate_key,
            signature=leaf_signature,
            message=payload,
            context="LEAF_KEY",
        )

    @classmethod
    def verify_certificate(
        cls,
        certificate_hash: bytes,
        certificate_signature: bytes,
        leaf_public_key: bytes,
        intermediate_cert: Dict[str, Any],
        expires_at: float,
        created_at: float,
        serial: str,
        trusted_current_time: float,
    ) -> bool:
        if trusted_current_time is None:
            raise RuntimeError("CRITICAL SECURITY ERROR: Trusted UTC time is required.")

        if trusted_current_time < created_at:
            raise RuntimeError("CRITICAL SECURITY ERROR: Certificate issued in the future.")

        if trusted_current_time > expires_at:
            raise RuntimeError("CRITICAL SECURITY ERROR: Certificate expired.")

        if not serial or not certificate_hash or not certificate_signature:
            raise RuntimeError("CRITICAL SECURITY ERROR: Incomplete certificate metadata.")

        if not cls.verify_leaf_key(leaf_public_key, intermediate_cert):
            return False

        # 2. Single-path verification for the assertion
        return StrictCryptographicEngine.verify_ecdsa_p384(
            public_key_der=leaf_public_key,
            signature=certificate_signature,
            message=certificate_hash,
            context="CERTIFICATE_ASSERTION",
        )