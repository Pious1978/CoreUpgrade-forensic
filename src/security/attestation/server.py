"""
Institutional Remote Hardware Attestation Server
"""

import os
import json
import subprocess
import tempfile
from typing import Dict, Any
from src.security.crypto import StrictCryptographicEngine


class RemoteAttestationServer:

    # Expected Golden PCR Baseline (PCRs 0,1,2,3,4,5,7,11)
    GOLDEN_PCR_MEASUREMENT_HASH = "8f3c72b11e1f9a...expected_sha384_hash_string..."
    AIK_ROOT_CA_PATH = "/etc/trading-engine/trust/aik_root_ca.der"

    @classmethod
    def process_attestation_request(cls, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates raw TPM quote evidence submitted by client nodes.
        """
        nonce = request_payload.get("nonce")
        quote_hex = request_payload.get("quote")
        signature_hex = request_payload.get("signature")
        pcr_blob_hex = request_payload.get("pcr_blob")

        if not all([nonce, quote_hex, signature_hex, pcr_blob_hex]):
            return {"status": "REJECTED", "reason": "Incomplete evidence payload"}

        quote_bytes = bytes.fromhex(quote_hex)
        sig_bytes = bytes.fromhex(signature_hex)
        pcr_bytes = bytes.fromhex(pcr_blob_hex)

        # 1. Verify PCR Measurement Hash against Golden Baseline
        recomputed_pcr_hash = StrictCryptographicEngine.sha384_hex(pcr_bytes)
        if recomputed_pcr_hash != cls.GOLDEN_PCR_MEASUREMENT_HASH:
            return {
                "status": "REJECTED",
                "reason": f"PCR Measurement Hash mismatch. Got {recomputed_pcr_hash}, expected {cls.GOLDEN_PCR_MEASUREMENT_HASH}"
            }

        # 2. Cryptographically Verify TPM Quote Signature via tpm2_checkquote
        with tempfile.TemporaryDirectory() as directory:
            q_path = os.path.join(directory, "quote.msg")
            s_path = os.path.join(directory, "quote.sig")
            p_path = os.path.join(directory, "pcr.bin")

            with open(q_path, "wb") as f: f.write(quote_bytes)
            with open(s_path, "wb") as f: f.write(sig_bytes)
            with open(p_path, "wb") as f: f.write(pcr_bytes)

            try:
                subprocess.run(
                    [
                        "tpm2_checkquote",
                        "-u", cls.AIK_ROOT_CA_PATH,
                        "-m", q_path,
                        "-s", s_path,
                        "-f", p_path,
                        "-q", nonce
                    ],
                    check=True,
                    timeout=5,
                    capture_output=True
                )
            except subprocess.CalledProcessError as exc:
                return {
                    "status": "REJECTED",
                    "reason": f"TPM Quote cryptographic check failed: {exc.stderr.decode()}"
                }

        # 3. Issue Attestation Verdict Token
        verdict_payload = {
            "status": "VALID",
            "pcr_hash": recomputed_pcr_hash,
            "nonce": nonce,
            "issued_at_utc": StrictCryptographicEngine.rfc8785_canonical_serialize({"t": "now"}).decode()
        }
        
        return verdict_payload