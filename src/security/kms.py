import os
import abc

class SigningProvider(abc.ABC):
    @abc.abstractmethod
    def sign_digest(self, key_id: str, digest: bytes) -> bytes:
        raise NotImplementedError

class AWSKMSProvider(SigningProvider):
    """
    SEC-001: Correct KMS integration using supported algorithms (ECDSA P384).
    """
    def __init__(self):
        try:
            import boto3
            # SEC-004: mTLS to HSM/KMS gateway would be configured here in boto3 Session
            self.client = boto3.client("kms", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        except ImportError:
            self.client = None

    def sign_digest(self, key_id: str, digest: bytes) -> bytes:
        if not self.client:
            raise RuntimeError("CRITICAL SECURITY ERROR: KMS client unavailable.")
            
        try:
            response = self.client.sign(
                KeyId=key_id,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm="ECDSA_SHA_384"
            )
            signature = response.get("Signature")
            if not signature:
                raise RuntimeError("CRITICAL SECURITY ERROR: Empty signature from KMS.")
            return signature
        except Exception as e:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: KMS signing failed: {str(e)}") from e