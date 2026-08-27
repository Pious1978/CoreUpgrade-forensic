from __future__ import annotations

import os
from typing import Final
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from src.security.kms.base import SigningProvider

class KMSPurpose:
    STARTUP_CERTIFICATE: Final[str] = "TRADING_ENGINE_STARTUP_CERTIFICATE_V1"
    INTERMEDIATE_CA: Final[str] = "TRADING_ENGINE_INTERMEDIATE_CA_V1"
    LEAF_KEY: Final[str] = "TRADING_ENGINE_LEAF_KEY_V1"
    CRL: Final[str] = "TRADING_ENGINE_CRL_V1"
    AUDIT: Final[str] = "TRADING_ENGINE_AUDIT_V1"
    ORDER_GATE: Final[str] = "TRADING_ENGINE_ORDER_GATE_V1"
    RECOVERY: Final[str] = "TRADING_ENGINE_RECOVERY_V1"

class AWSKMSProvider(SigningProvider):
    """
    AWS KMS asymmetric ECDSA P-384 signing provider.

    IMPORTANT: AWS KMS EncryptionContext is intentionally NOT used.
    EncryptionContext is not supported for asymmetric KMS signing keys. 
    Domain separation is instead performed before the digest reaches KMS.
    """

    ALGORITHM: Final[str] = "ECDSA_SHA_384"
    DIGEST_LENGTH: Final[int] = 48
    EXECUTION_GATE_PURPOSE: Final[str] = KMSPurpose.ORDER_GATE

    def __init__(self, region: str | None = None, execution_gate_key_arn: str | None = None) -> None:
        self.region = region or os.environ.get("AWS_REGION") or "ap-south-1"
        self.environment = os.environ.get("TE_ENVIRONMENT") or "UNKNOWN"
        self.execution_gate_key_arn = execution_gate_key_arn or os.environ.get("TE_EXECUTION_GATE_KMS_KEY_ARN")

        if not self.execution_gate_key_arn:
            raise RuntimeError("CRITICAL SECURITY ERROR: TE_EXECUTION_GATE_KMS_KEY_ARN is not configured.")

        if self.environment != "PRODUCTION":
            raise RuntimeError("CRITICAL SECURITY ERROR: AWS KMS execution signing is only permitted in PRODUCTION.")

        self.client = boto3.client("kms", region_name=self.region)

    def sign_execution_gate_digest(self, digest: bytes, certificate_serial: str) -> bytes:
        if not isinstance(digest, bytes): raise TypeError("digest must be bytes")
        
        if len(digest) != self.DIGEST_LENGTH:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Execution-gate digest must be exactly {self.DIGEST_LENGTH} bytes.")

        if not certificate_serial or len(certificate_serial) > 256:
            raise RuntimeError("CRITICAL SECURITY ERROR: Certificate serial is required and must not exceed length.")

        try:
            response = self.client.sign(
                KeyId=self.execution_gate_key_arn,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm=self.ALGORITHM,
            )

            signature = response.get("Signature")
            if not signature:
                raise RuntimeError("CRITICAL SECURITY ERROR: AWS KMS returned an empty signature.")

            return signature

        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: AWS KMS execution-gate signing failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Unexpected KMS signing failure: {exc}") from exc

    def sign_digest(self, key_id: str, digest: bytes, purpose: str, certificate_serial: str) -> bytes:
        if key_id != self.execution_gate_key_arn:
            raise RuntimeError("CRITICAL SECURITY ERROR: Unauthorized KMS key requested.")

        if purpose != self.EXECUTION_GATE_PURPOSE:
            raise RuntimeError("CRITICAL SECURITY ERROR: Unauthorized KMS signing purpose.")

        return self.sign_execution_gate_digest(digest=digest, certificate_serial=certificate_serial)

    def get_public_key(self, key_id: str) -> bytes:
        if key_id != self.execution_gate_key_arn:
            raise RuntimeError("CRITICAL SECURITY ERROR: Unauthorized KMS public-key request.")

        try:
            response = self.client.get_public_key(KeyId=key_id)
            public_key = response.get("PublicKey")

            if not public_key:
                raise RuntimeError("CRITICAL SECURITY ERROR: AWS KMS returned an empty public key.")

            return public_key

        except (ClientError, BotoCoreError) as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: AWS KMS public-key retrieval failed: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Unexpected KMS public-key failure: {exc}") from exc