"""
Audit Artifact Envelope

Defines the immutable container for all audit artifacts produced
by individual gates, ensuring permanent identity and versioning.
Resides in the shared core domain layer to prevent layer inversion.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class AuditArtifactEnvelope:

    artifact_id: str
    artifact_type: str
    schema_version: str
    generated_at: str
    generator: str
    fingerprint: str
    payload: Dict[str, Any]

    @classmethod
    def create(
        cls,
        artifact_type: str,
        schema_version: str,
        generated_at: str,
        generator: str,
        fingerprint: str,
        payload: Dict[str, Any]
    ) -> "AuditArtifactEnvelope":
        """
        Factory method to instantiate an envelope with a computed permanent identity.
        """
        artifact_id = f"{artifact_type}:{fingerprint}"
        
        return cls(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            schema_version=schema_version,
            generated_at=generated_at,
            generator=generator,
            fingerprint=fingerprint,
            payload=payload
        )
