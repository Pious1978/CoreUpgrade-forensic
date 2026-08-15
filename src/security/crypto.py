"""
Institutional Cryptographic Verification Layer.

Security objectives:
- CRYPTO-001: Approved asymmetric algorithms only (ECDSA P-384 + SHA-384).
- CRYPTO-002: Domain separation / signature context binding for every operation.
- CRYPTO-003: RFC8785 canonical JSON serialization to prevent payload malleability.
- CRYPTO-004: Strict input validation and fail-closed state if dependencies missing.

IMPORTANT:
Python is NOT a root of trust. No private keys exist within this environment.
This module only performs deterministic digest construction and signature verification.
All signing operations happen inside isolated hardware (AWS KMS/HSM).
"""

from __future__ import annotations

import hashlib
from typing import Any, Final

try:
    import rfc8785
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric import utils
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    InvalidSignature = Exception


class CryptoPolicy:
    """
    Central cryptographic policy.

    The institutional trading engine strictly enforces:
        ECDSA P-384 curve
        SHA-384 hashing
    """

    ALLOWED_SIGNATURE_ALGORITHMS: Final[frozenset[str]] = frozenset(
        {"ECDSA_P384_SHA384"}
    )

    HASH_DIGEST_SIZE: Final[int] = 48


class StrictCryptographicEngine:
    """
    Institutional cryptographic boundary.

    Security properties:
    1. Every signature operation is explicitly domain separated.
    2. Canonical serialization strictly follows RFC 8785.
    3. ECDSA public keys are required to be secp384r1.
    4. SHA-384 is used consistently across all domains.
    5. AWS KMS receives an already-computed, context-bound 48-byte digest.
    6. Unknown cryptographic contexts instantly fail closed.

    AWS KMS asymmetric Sign operations do NOT support EncryptionContext. 
    Therefore, domain separation is enforced cryptographically by hashing:
        SHA384( context || canonical_message )
    """

    # Cryptographic Domain Separation Contexts
    # Prevents signature replay attacks across different subsystems.
    CONTEXTS: Final[dict[str, bytes]] = {
        "INTERMEDIATE_CA": b"TRADING_ENGINE_INTERMEDIATE_CA_V1\x00",
        "LEAF_KEY": b"TRADING_ENGINE_LEAF_KEY_V1\x00",
        "CERTIFICATE_ASSERTION": b"TRADING_ENGINE_CERTIFICATE_ASSERTION_V1\x00",
        "CRL": b"TRADING_ENGINE_CRL_V1\x00",
        "AUDIT": b"TRADING_ENGINE_AUDIT_V1\x00",
        "ORDER_GATE": b"TRADING_ENGINE_ORDER_GATE_V1\x00",
        "RECOVERY": b"TRADING_ENGINE_RECOVERY_V1\x00",
    }

    @classmethod
    def require_crypto(cls) -> None:
        """
        Fails closed if the environment lacks required cryptographic primitives.
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "Required cryptographic dependencies are unavailable."
            )

    @classmethod
    def context(cls, name: str) -> bytes:
        """
        Return a registered cryptographic domain-separation prefix.
        Unknown contexts are never accepted.
        """
        try:
            return cls.CONTEXTS[name]
        except KeyError as exc:
            raise RuntimeError(
                f"CRITICAL SECURITY ERROR: Unknown cryptographic context: {name}"
            ) from exc

    @classmethod
    def rfc8785_canonical_serialize(cls, payload: Any) -> bytes:
        """
        Serialize an object according to RFC 8785 JSON Canonicalization.
        Prevents key reordering, float manipulation, or unicode encoding attacks.
        """
        cls.require_crypto()

        try:
            return rfc8785.dumps(payload)
        except Exception as exc:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                f"RFC8785 canonicalization failed: {exc}"
            ) from exc

    @staticmethod
    def sha384_digest(payload: bytes) -> bytes:
        """
        Return the raw 48-byte SHA-384 digest of the given payload.
        """
        if not isinstance(payload, bytes):
            raise TypeError("SHA-384 input must be bytes.")

        return hashlib.sha384(payload).digest()

    @classmethod
    def context_bound_message(cls, message: bytes, context: str) -> bytes:
        """
        Construct the exact byte sequence covered by the signature:
            context || message

        This method centralizes the byte layout so signing and verification
        can never accidentally diverge.
        """
        if not isinstance(message, bytes):
            raise TypeError("Signed message must be bytes.")

        return cls.context(context) + message

    @classmethod
    def compute_signing_digest(cls, message: bytes, context: str) -> bytes:
        """
        Compute the exact SHA-384 digest that must be supplied to AWS KMS
        when using MessageType = DIGEST and SigningAlgorithm = ECDSA_SHA_384.

        Result is always exactly 48 bytes.
        """
        signed_payload = cls.context_bound_message(
            message=message,
            context=context,
        )

        digest = cls.sha384_digest(signed_payload)

        if len(digest) != CryptoPolicy.HASH_DIGEST_SIZE:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "SHA-384 digest length invariant violated."
            )

        return digest

    @classmethod
    def compute_kms_signing_digest(cls, message: bytes, context: str) -> bytes:
        """
        Explicit AWS KMS helper alias for clarity in external modules.
        Equivalent to compute_signing_digest().
        """
        return cls.compute_signing_digest(
            message=message,
            context=context,
        )

    @classmethod
    def verify_ecdsa_p384(
        cls,
        public_key_der: bytes,
        signature: bytes,
        message: bytes,
        context: str,
    ) -> bool:
        """
        Verify an ECDSA P-384 / SHA-384 signature over a raw message.

        The exact verified content is:
            SHA384(context || message)
        """
        cls.require_crypto()

        if not isinstance(public_key_der, bytes):
            raise TypeError("public_key_der must be bytes.")
        if not isinstance(signature, bytes):
            raise TypeError("signature must be bytes.")
        if not isinstance(message, bytes):
            raise TypeError("message must be bytes.")

        try:
            public_key = load_der_public_key(public_key_der)

            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                return False

            if public_key.curve.name != "secp384r1":
                return False

            signed_payload = cls.context_bound_message(
                message=message,
                context=context,
            )

            public_key.verify(
                signature,
                signed_payload,
                ec.ECDSA(hashes.SHA384()),
            )

            return True

        except InvalidSignature:
            return False
        except Exception as exc:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                f"ECDSA P-384 verification failed: {exc}"
            ) from exc

    @staticmethod
    def verify_ecdsa_p384_digest(
        public_key_der: bytes,
        signature: bytes,
        digest: bytes,
    ) -> bool:
        """
        Verify an ECDSA P-384 signature against an already-computed 48-byte digest.
        Used primarily when validating signatures directly corresponding to KMS outputs.
        """
        StrictCryptographicEngine.require_crypto()

        if not isinstance(public_key_der, bytes):
            raise TypeError("public_key_der must be bytes.")
        if not isinstance(signature, bytes):
            raise TypeError("signature must be bytes.")
        if not isinstance(digest, bytes):
            raise TypeError("digest must be bytes.")

        if len(digest) != CryptoPolicy.HASH_DIGEST_SIZE:
            raise RuntimeError(
                f"CRITICAL SECURITY ERROR: ECDSA SHA-384 digest must be exactly {CryptoPolicy.HASH_DIGEST_SIZE} bytes."
            )

        try:
            public_key = load_der_public_key(public_key_der)

            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                return False

            if public_key.curve.name != "secp384r1":
                return False

            public_key.verify(
                signature,
                digest,
                ec.ECDSA(utils.Prehashed(hashes.SHA384())),
            )
            return True

        except InvalidSignature:
            return False
        except Exception as exc:
            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                f"Cryptographic prehashed digest verification failed: {exc}"
            ) from exc