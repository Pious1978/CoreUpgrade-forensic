import time
import uuid
import hashlib
from typing import Dict, Any
from src.security.certificate import StartupCertificate
from src.security.crypto import StrictCryptographicEngine
from src.security.kms import ExternalHardwareSecurityModule
from src.security.fingerprint import HardwareIdentity

class CertificateIssuer:
    @staticmethod
    def issue(
        manifest: Dict[str, Any],
        env_hash: str,
        gate_timings: Dict[str, float],
        signing_mode: str,
        dependency_graph_hash: str,
        empirical_proof_hash: str,
        boot_counter: int,
        theorem_bytecode_hashes: Dict[str, str]
    ) -> StartupCertificate:
        sig_meta = manifest.get("signature_metadata", {})
        created_at = time.time()
        expires_at = created_at + 86400.0
        max_runtime_seconds = 86400.0
        issued_monotonic_time = time.perf_counter()
        
        algorithm = sig_meta.get("algorithm", "Ed25519")
        key_id = sig_meta.get("key_id", "default-key-id")
        public_key = sig_meta.get("public_key", "")
        signature_version = sig_meta.get("signature_version", "v1")
        issuer = sig_meta.get("issuer", "SystemRootAuthority")
        serial = sig_meta.get("serial", str(uuid.uuid4()))
        rotation_generation = sig_meta.get("rotation_generation", 1)
        boot_nonce = uuid.uuid4().hex
        process_uuid = str(uuid.uuid4())
        
        machine_id_raw = HardwareIdentity.get_machine_hardware_identity()
        machine_identity_hash = hashlib.sha256(machine_id_raw.encode("utf-8")).hexdigest()

        policy = manifest.get("policy_permissions", {})
        allowed_strategy_hashes = policy.get("allowed_strategy_hashes", [])
        allowed_accounts = policy.get("allowed_accounts", [])
        max_order_notional = policy.get("max_order_notional", 1000000.0)
        
        chain_payload = {
            "algorithm": algorithm,
            "key_id": key_id,
            "public_key": public_key,
            "signature_version": signature_version,
            "created_at": created_at,
            "expires_at": expires_at,
            "max_runtime_seconds": max_runtime_seconds,
            "issued_monotonic_time": issued_monotonic_time,
            "issuer": issuer,
            "serial": serial,
            "rotation_generation": rotation_generation,
            "signing_mode": signing_mode,
            "boot_nonce": boot_nonce,
            "process_uuid": process_uuid,
            "boot_counter": boot_counter,
            "machine_identity_hash": machine_identity_hash,
            "registry_hash": manifest.get("registry_hash", ""),
            "dependency_graph_hash": dependency_graph_hash,
            "empirical_proof_hash": empirical_proof_hash,
            "env_fingerprint_hash": env_hash,
            "gate_timings": gate_timings,
            "theorem_bytecode_hashes": sorted(list(theorem_bytecode_hashes.items())),
            "allowed_strategy_hashes": sorted(allowed_strategy_hashes),
            "allowed_accounts": sorted(allowed_accounts),
            "max_order_notional": max_order_notional
        }
        chain_bytes = StrictCryptographicEngine.canonical_serialize(chain_payload)
        certificate_hash = hashlib.sha256(chain_bytes).hexdigest()
        
        certificate_signature = ExternalHardwareSecurityModule.sign_certificate(key_id, certificate_hash)

        return StartupCertificate(
            algorithm=algorithm,
            key_id=key_id,
            public_key=public_key,
            signature_version=signature_version,
            created_at=created_at,
            expires_at=expires_at,
            max_runtime_seconds=max_runtime_seconds,
            issued_monotonic_time=issued_monotonic_time,
            issuer=issuer,
            serial=serial,
            rotation_generation=rotation_generation,
            signing_mode=signing_mode,
            boot_nonce=boot_nonce,
            process_uuid=process_uuid,
            boot_counter=boot_counter,
            machine_identity_hash=machine_identity_hash,
            process_start_time=time.perf_counter(),
            registry_hash=manifest.get("registry_hash", ""),
            dependency_graph_hash=dependency_graph_hash,
            empirical_proof_hash=empirical_proof_hash,
            env_fingerprint_hash=env_hash,
            gate_timings=gate_timings,
            theorem_bytecode_hashes=theorem_bytecode_hashes,
            allowed_strategy_hashes=allowed_strategy_hashes,
            allowed_accounts=allowed_accounts,
            max_order_notional=max_order_notional,
            certificate_hash=certificate_hash,
            certificate_signature=certificate_signature
        )