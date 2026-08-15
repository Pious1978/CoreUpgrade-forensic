from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True, slots=True)
class StartupCertificate:
    """
    Immutable startup authorization certificate.
    Tuple-based policy fields prevent accidental mutation of strategy/account authorization collections.
    """
    algorithm: str
    key_id: str

    leaf_public_key: bytes

    certificate_hash: bytes
    certificate_signature: bytes

    intermediate_certificate: Tuple[Tuple[str, str], ...]

    serial: str

    created_at: float
    expires_at: float

    rotation_generation: int

    tpm_quote_hash: str
    hardware_boot_counter: int
    boot_nonce: str

    container_digest: str
    sbom_hash: str
    slsa_provenance_hash: str

    process_uuid: str
    dependency_graph_hash: str
    registry_hash: str

    allowed_strategy_hashes: Tuple[str, ...]
    allowed_accounts: Tuple[str, ...]

    max_order_notional: float
    max_velocity_1s: float

    issuer: str

    signature_version: str = "1.0"

    def __post_init__(self) -> None:
        self.validate_policy_fields()

    def validate_policy_fields(self) -> None:
        if self.algorithm != "ECDSA_P384_SHA384":
            raise RuntimeError("CRITICAL SECURITY ERROR: Unsupported certificate algorithm.")

        if not self.key_id:
            raise RuntimeError("Certificate key ID missing.")

        if not self.leaf_public_key:
            raise RuntimeError("Certificate leaf public key missing.")

        if not self.serial:
            raise RuntimeError("Certificate serial missing.")

        if self.expires_at <= self.created_at:
            raise RuntimeError("Certificate expiration must be after creation.")

        for value in [self.max_order_notional, self.max_velocity_1s, self.created_at, self.expires_at]:
            if not math.isfinite(value):
                raise RuntimeError("CRITICAL SECURITY ERROR: Non-finite certificate numeric value detected.")

        if self.rotation_generation < 1:
            raise RuntimeError("Invalid key rotation generation.")

        if not self.allowed_strategy_hashes:
            raise RuntimeError("Certificate contains no strategy permissions.")

        if not self.allowed_accounts:
            raise RuntimeError("Certificate contains no account permissions.")

        if self.max_order_notional <= 0:
            raise RuntimeError("Invalid maximum order notional.")

        if self.max_velocity_1s <= 0:
            raise RuntimeError("Invalid one-second velocity limit.")

        if not self.issuer:
            raise RuntimeError("Certificate issuer missing.")