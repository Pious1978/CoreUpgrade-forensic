"""
src/runtime/crl.py

Institutional Certificate Revocation Registry.

Security model:

Root CA
    |
    | signs
    |
CRL Document
    |
    | verified by runtime
    |
Execution admission decision


Security controls:

PKI-001:
    CRL freshness enforcement

PKI-002:
    Root CA signed CRL

PKI-003:
    Prevent CRL replay

PKI-004:
    Fail closed when revocation state unknown

CRYPTO-002:
    Domain separated CRL signatures
"""

import os
import json
import threading
from typing import Dict, Any


from src.security.crypto import (
    StrictCryptographicEngine
)

from src.security.pki import (
    RootPKIAuthority
)

from src.security.time import (
    TrustedTimeProvider
)

from src.security.audit import (
    SecurityAuditLogger
)


class RevocationRegistry:
    """
    Runtime Certificate Revocation Authority.

    Trading execution MUST NOT continue when:

    - CRL missing
    - CRL expired
    - CRL signature invalid
    - CRL malformed
    """

    _lock = threading.RLock()


    _CRL_PATH = (
        "/etc/trading-engine/trust/crl.json"
    )


    # Maximum allowed CRL age.
    #
    # Institutional systems normally use:
    #
    # 5 minutes for active trading systems
    #
    MAX_CRL_AGE_SECONDS = 300



    # ------------------------------------------------------------------
    # CRL loading
    # ------------------------------------------------------------------

    @classmethod
    def _load_crl_file(cls) -> Dict[str, Any]:

        if not os.path.exists(
            cls._CRL_PATH
        ):

            SecurityAuditLogger.log_event(
                "CRL_FAILURE",
                "CRL file missing",
                {
                    "path": cls._CRL_PATH
                }
            )


            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL file missing."
            )



        try:

            with open(
                cls._CRL_PATH,
                "rb"
            ) as file:

                raw = file.read()



            return json.loads(
                raw.decode("utf-8")
            )


        except Exception as exc:


            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                f"CRL parsing failed: {exc}"
            ) from exc



    # ------------------------------------------------------------------
    # CRL cryptographic verification
    # ------------------------------------------------------------------

    @classmethod
    def _verify_crl_signature(
        cls,
        crl_data: Dict[str, Any]
    ) -> Dict[str, Any]:


        signature_hex = crl_data.get(
            "signature"
        )


        if not signature_hex:

            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL signature missing."
            )



        # Remove signature before verification

        unsigned_crl = dict(
            crl_data
        )

        unsigned_crl.pop(
            "signature",
            None
        )


        serialized = (
            StrictCryptographicEngine
            .canonical_serialize(
                unsigned_crl
            )
        )



        root_key = (
            RootPKIAuthority
            .get_root_pubkey_bytes()
        )



        verified = (
            StrictCryptographicEngine
            .verify_ecdsa_p384(
                public_key_bytes=root_key,

                signature_bytes=bytes.fromhex(
                    signature_hex
                ),

                message_bytes=serialized,

                context_prefix=(
                    StrictCryptographicEngine
                    .CONTEXT_CRL
                )
            )
        )


        if not verified:


            SecurityAuditLogger.log_event(
                "CRL_SIGNATURE_FAILURE",
                "CRL root signature invalid"
            )


            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL signature verification failed."
            )



        return unsigned_crl



    # ------------------------------------------------------------------
    # CRL freshness verification
    # ------------------------------------------------------------------

    @classmethod
    def _verify_freshness(
        cls,
        crl_data: Dict[str, Any],
        trusted_time: float
    ):


        issued_at = crl_data.get(
            "issued_at_utc"
        )


        expires_at = crl_data.get(
            "expires_at_utc"
        )


        if not issued_at or not expires_at:

            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL missing timestamp fields."
            )



        # Future dated CRL attack

        if issued_at > trusted_time:

            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL issued in future."
            )



        age = (
            trusted_time -
            issued_at
        )



        if age > cls.MAX_CRL_AGE_SECONDS:


            SecurityAuditLogger.log_event(
                "CRL_STALE",
                "CRL exceeded maximum age",
                {
                    "age_seconds": age
                }
            )


            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL is stale."
            )



        # Expiry check

        if trusted_time > expires_at:

            raise RuntimeError(
                "CRITICAL SECURITY ERROR: "
                "CRL expired."
            )



    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def get_verified_crl(cls) -> Dict[str, Any]:

        with cls._lock:


            trusted_time = (
                TrustedTimeProvider
                .get_trusted_utc_time()
            )


            crl = cls._load_crl_file()


            unsigned_crl = (
                cls._verify_crl_signature(
                    crl
                )
            )


            cls._verify_freshness(
                unsigned_crl,
                trusted_time
            )


            return unsigned_crl



    # ------------------------------------------------------------------
    # Certificate revocation check
    # ------------------------------------------------------------------

    @classmethod
    def is_revoked(
        cls,
        serial: str,
        certificate_hash: str
    ) -> bool:


        crl = (
            cls.get_verified_crl()
        )


        revoked_serials = set(
            crl.get(
                "revoked_serials",
                []
            )
        )


        revoked_hashes = set(
            crl.get(
                "revoked_certificate_hashes",
                []
            )
        )



        revoked = (
            serial in revoked_serials
            or
            certificate_hash in revoked_hashes
        )



        if revoked:


            SecurityAuditLogger.log_event(
                "CERTIFICATE_REVOKED",
                "Certificate found in CRL",
                {
                    "serial": serial,
                    "certificate_hash": certificate_hash
                }
            )



        return revoked