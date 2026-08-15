import os
import boto3
from src.security.kms.base import SigningProvider

class InstitutionalKMSProvider(SigningProvider):
    """
    CRITICAL-003: KMS with Strict IAM Context Binding.
    CRYPTO-001: Utilizing ECDSA P384 for native Cloud HSM compatibility.
    """
    def __init__(self):
        self.client = boto3.client("kms", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self.environment = os.environ.get("TE_ENVIRONMENT", "PRODUCTION")

    def sign_digest(self, key_id: str, digest: bytes, serial: str, purpose: str) -> bytes:
        if not self.client:
            raise RuntimeError("CRITICAL: KMS client unavailable.")
            
        # CRYPTO-002: Strict Context Binding enforced via KMS IAM Policies
        # The AWS IAM Role MUST require this exact EncryptionContext to allow kms:Sign
        encryption_context = {
            "service": "institutional-trading-engine",
            "environment": self.environment,
            "purpose": purpose,
            "certificate_serial": serial
        }
        
        try:
            response = self.client.sign(
                KeyId=key_id,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm="ECDSA_SHA_384",
                EncryptionContext=encryption_context
            )
            return response["Signature"]
        except Exception as e:
            raise RuntimeError(f"CRITICAL: Context-bound KMS signing failed: {str(e)}") from e