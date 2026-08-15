from __future__ import annotations

from typing import Any
from src.security.crypto import StrictCryptographicEngine
from src.security.kms.aws_kms import AWSKMSProvider, KMSPurpose

class ExecutionGateSigner:
    """
    Institutional execution-gate signing boundary.
    Responsibilities:
    1. Canonicalize the order authorization payload.
    2. Apply ORDER_GATE domain separation.
    3. SHA-384 the resulting bytes.
    4. Send exactly the 48-byte digest to AWS KMS.
    """
    CONTEXT: str = "ORDER_GATE"
    PURPOSE: str = KMSPurpose.ORDER_GATE

    def __init__(self, kms_provider: AWSKMSProvider | None = None) -> None:
        self.kms = kms_provider or AWSKMSProvider()

    def build_authorization_digest(self, authorization_payload: Any) -> bytes:
        canonical_payload = StrictCryptographicEngine.rfc8785_canonical_serialize(authorization_payload)
        digest = StrictCryptographicEngine.compute_signing_digest(message=canonical_payload, context=self.CONTEXT)

        if len(digest) != 48:
            raise RuntimeError("CRITICAL SECURITY ERROR: Execution-gate digest is not SHA-384.")

        return digest

    def sign(self, authorization_payload: Any, certificate_serial: str) -> bytes:
        if not certificate_serial:
            raise RuntimeError("CRITICAL SECURITY ERROR: Certificate serial missing.")

        digest = self.build_authorization_digest(authorization_payload)

        return self.kms.sign_execution_gate_digest(digest=digest, certificate_serial=certificate_serial)