from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TPMQuoteEvidence:
    nonce: str
    quote: bytes
    signature: bytes
    pcr_blob: bytes
    measurement_hash: str

class TPM2HardwareAttestation:
    REQUIRED_PCR_BANK = "sha256:0,1,2,3,4,5,7,11"
    DEFAULT_AIK_PUBLIC = "/etc/trading-engine/trust/aik.pub"

    @staticmethod
    def generate_nonce() -> str:
        return os.urandom(32).hex()

    @classmethod
    def generate_quote(cls, nonce: str) -> TPMQuoteEvidence:
        aik_public_key = os.environ.get("TPM_AIK_PUBLIC", cls.DEFAULT_AIK_PUBLIC)

        if not os.path.isfile(aik_public_key):
            raise RuntimeError("CRITICAL SECURITY ERROR: TPM AIK public key missing.")

        with tempfile.TemporaryDirectory(prefix="trading-engine-tpm-") as directory:
            quote_file = os.path.join(directory, "quote.msg")
            signature_file = os.path.join(directory, "quote.sig")
            pcr_file = os.path.join(directory, "pcr.bin")

            try:
                subprocess.run(
                    [
                        "tpm2_quote", "-c", "aik.ctx", "-l", cls.REQUIRED_PCR_BANK,
                        "-q", nonce, "-m", quote_file, "-s", signature_file, "-p", pcr_file,
                    ],
                    check=True, timeout=5, capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
                raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM quote generation failed: {stderr}") from exc
            except Exception as exc:
                raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM quote generation failed: {exc}") from exc

            try:
                subprocess.run(
                    [
                        "tpm2_checkquote", "-u", aik_public_key, "-m", quote_file,
                        "-s", signature_file, "-f", pcr_file, "-q", nonce,
                    ],
                    check=True, timeout=5, capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
                raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM quote verification failed: {stderr}") from exc
            except Exception as exc:
                raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM verification failure: {exc}") from exc

            try:
                with open(quote_file, "rb") as handle: quote_data = handle.read()
                with open(signature_file, "rb") as handle: sig_data = handle.read()
                with open(pcr_file, "rb") as handle: pcr_data = handle.read()
            except OSError as exc:
                raise RuntimeError(f"CRITICAL SECURITY ERROR: Unable to read verified TPM data: {exc}") from exc

            if not pcr_data:
                raise RuntimeError("CRITICAL SECURITY ERROR: TPM returned empty PCR data.")

            measurement_hash = hashlib.sha384(pcr_data).hexdigest()

            return TPMQuoteEvidence(
                nonce=nonce,
                quote=quote_data,
                signature=sig_data,
                pcr_blob=pcr_data,
                measurement_hash=measurement_hash
            )

class TPMMonotonicCounter:
    NV_INDEX = "0x01500001"

    @classmethod
    def increment(cls) -> int:
        try:
            subprocess.run(["tpm2_nvincrement", "-C", "o", cls.NV_INDEX], check=True, timeout=5, capture_output=True)
            return cls.read()
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM NV increment failed: {stderr}") from exc
        except Exception as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM NV increment failed: {exc}") from exc

    @classmethod
    def read(cls) -> int:
        try:
            result = subprocess.run(["tpm2_nvread", "-C", "o", "-s", "8", cls.NV_INDEX], capture_output=True, check=True, timeout=5)
            if len(result.stdout) != 8:
                raise RuntimeError("CRITICAL SECURITY ERROR: Unexpected TPM NV counter size.")
            return int.from_bytes(result.stdout, "big")
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM NV read failed: {stderr}") from exc
        except Exception as exc:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: TPM NV read failed: {exc}") from exc