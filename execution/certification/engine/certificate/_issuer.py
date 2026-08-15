"""
Cryptographic Certificate Issuer & Verifier

Authority:
    Execution Layer Cryptographic Certificate Issuance & Audit Verification
"""
import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from research.governance.serialization import CanonicalSerializer

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
except ImportError:
    Ed25519PrivateKey = None
    Ed25519PublicKey = None

@dataclass(frozen=True, slots=True)
class StartupCertificate:
    certified: bool
    manifest_id: str
    manifest_schema_version: str
    engine_version: str
    registry_hash: str
    registry_signature: str
    environment_hash: str
    timestamp: str
    total_theorems: int
    gates_passed: Dict[str, float]
    empirical_proof_hash: Optional[str] = None
    startup_certificate_hash: Optional[str] = None
    certificate_signature: Optional[str] = None

    def persist(self, directory: str = "certificates") -> str:
        os.makedirs(directory, exist_ok=True)
        filename = f"startup_certificate_{self.startup_certificate_hash[:16]}.json"
        filepath = os.path.join(directory, filename)
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True, indent=2))
        return filepath

class CertificateIssuer:
    @staticmethod
    def issue(
        *,
        manifest: Any,
        env_hash: str,
        gate_timings: Dict[str, float],
        empirical_proof_hash: str,
        total_theorems: int,
        signing_mode: str = "ED25519",
        private_key_bytes: Optional[bytes] = None
    ) -> StartupCertificate:
        manifest_dict = manifest.to_dict()
        timestamp = str(datetime.now(timezone.utc).timestamp())
        
        partial_cert = {
            "certified": True,
            "manifest_id": manifest_dict.get("manifest_id"),
            "manifest_schema_version": manifest_dict.get("schema_version"),
            "engine_version": manifest_dict.get("engine_version"),
            "registry_hash": manifest_dict.get("registry_hash"),
            "registry_signature": manifest_dict.get("signature"),
            "environment_hash": env_hash,
            "timestamp": timestamp,
            "total_theorems": total_theorems,
            "gates_passed": gate_timings,
            "empirical_proof_hash": empirical_proof_hash,
        }
        startup_certificate_hash = CanonicalSerializer.digest(partial_cert)

        if signing_mode == "development":
            cert_signature = "UNSIGNED_DEV_MODE"
        else:
            if Ed25519PrivateKey is None or private_key_bytes is None:
                raise RuntimeError("Ed25519 private key required for certificate signing.")
            priv_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            cert_sig_bytes = priv_key.sign(bytes.fromhex(startup_certificate_hash))
            cert_signature = cert_sig_bytes.hex()

        return StartupCertificate(
            certified=True,
            manifest_id=partial_cert["manifest_id"],
            manifest_schema_version=partial_cert["manifest_schema_version"],
            engine_version=partial_cert["engine_version"],
            registry_hash=partial_cert["registry_hash"],
            registry_signature=partial_cert["registry_signature"],
            environment_hash=env_hash,
            timestamp=timestamp,
            total_theorems=total_theorems,
            gates_passed=gate_timings,
            empirical_proof_hash=empirical_proof_hash,
            startup_certificate_hash=startup_certificate_hash,
            certificate_signature=cert_signature
        )

    @staticmethod
    def verify(certificate: StartupCertificate, public_key_bytes: Optional[bytes] = None, environment: str = "production") -> bool:
        if not certificate.certified:
            return False
        
        partial_cert = {
            "certified": certificate.certified,
            "manifest_id": certificate.manifest_id,
            "manifest_schema_version": certificate.manifest_schema_version,
            "engine_version": certificate.engine_version,
            "registry_hash": certificate.registry_hash,
            "registry_signature": certificate.registry_signature,
            "environment_hash": certificate.environment_hash,
            "timestamp": certificate.timestamp,
            "total_theorems": certificate.total_theorems,
            "gates_passed": certificate.gates_passed,
            "empirical_proof_hash": certificate.empirical_proof_hash,
        }
        recalculated_hash = CanonicalSerializer.digest(partial_cert)
        if recalculated_hash != certificate.startup_certificate_hash:
            return False

        if certificate.certificate_signature == "UNSIGNED_DEV_MODE":
            if environment != "development":
                return False
            return True

        if public_key_bytes is None or Ed25519PublicKey is None:
            return False

        try:
            pub_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            pub_key.verify(bytes.fromhex(certificate.certificate_signature), bytes.fromhex(certificate.startup_certificate_hash))
            return True
        except Exception:
            return False
