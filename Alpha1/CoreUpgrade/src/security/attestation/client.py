"""
Production Remote Attestation Client
"""

import os
import requests
from typing import Dict, Any
from src.security.hardware import TPM2HardwareAttestation, TPMQuoteEvidence


class RemoteAttestationClient:

    @classmethod
    def request_remote_attestation(cls) -> Dict[str, Any]:
        """
        Generates local TPM quote evidence and submits it to the remote attestation server.
        """
        server_url = os.environ.get("TE_ATTESTATION_SERVER_URL")
        if not server_url:
            raise RuntimeError("CRITICAL SECURITY ERROR: TE_ATTESTATION_SERVER_URL environment variable is unconfigured.")

        # 1. Generate Local TPM Evidence
        nonce = TPM2HardwareAttestation.generate_nonce()
        evidence: TPMQuoteEvidence = TPM2HardwareAttestation.generate_quote(nonce)

        payload = {
            "nonce": evidence.nonce,
            "quote": evidence.quote.hex(),
            "signature": evidence.signature.hex(),
            "pcr_blob": evidence.pcr_blob.hex(),
            "measurement_hash": evidence.measurement_hash
        }

        # 2. Transmit to Attestation Server
        try:
            response = requests.post(
                f"{server_url}/v1/attest",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=3.0
            )
            response.raise_for_status()
            verdict = response.json()

            if verdict.get("status") != "VALID":
                reason = verdict.get("reason", "Unknown attestation failure")
                raise RuntimeError(f"CRITICAL SECURITY ERROR: Remote Attestation Denied: {reason}")

            return verdict

        except Exception as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Remote attestation communication failed: {exc}") from exc