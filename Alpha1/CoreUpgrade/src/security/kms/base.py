from __future__ import annotations
from abc import ABC, abstractmethod

class SigningProvider(ABC):
    """
    Abstract interface for institutional signing providers.
    The provider receives an already-domain-separated SHA-384 digest.
    It must NEVER silently hash the data again.
    """
    @abstractmethod
    def sign_digest(self, key_id: str, digest: bytes, purpose: str, certificate_serial: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def get_public_key(self, key_id: str) -> bytes:
        raise NotImplementedError