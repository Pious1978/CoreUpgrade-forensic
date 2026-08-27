"""
Institutional Audit Evidence Layer.

Properties:
- append only
- cryptographically chained (RFC8785)
- externally anchored to KMS
- execution-aware
- failure closed
"""

import os
import json
import hashlib
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from src.security.kms.aws_kms import AWSKMSProvider
from src.security.crypto import StrictCryptographicEngine


class ImmutableAuditLedger:

    LOG_FILE = "/var/log/trading-engine/audit/events.log"
    ANCHOR_INTERVAL = 100

    _lock = threading.RLock()
    _last_hash = "GENESIS_AUDIT_HASH_000000000000000000000000000000000000000000000000"
    _events_since_anchor = 0
    _pending: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def reserve_event(cls, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Phase 1: Creates immutable intent record.
        No trade execution should happen without reservation.
        """
        with cls._lock:
            reservation_id = "AUD-" + uuid.uuid4().hex

            reservation = {
                "reservation_id": reservation_id,
                "event_type": event_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "state": "RESERVED"
            }

            cls._pending[reservation_id] = reservation
            cls._write_raw({"reservation": reservation})
            
            return reservation_id

    @classmethod
    def commit_event(cls, reservation_id: str, status: str, metadata: Dict[str, Any] = None) -> None:
        """
        Phase 2: Cryptographically binds and commits the audit record.
        """
        with cls._lock:
            if reservation_id not in cls._pending:
                raise RuntimeError("CRITICAL SECURITY ERROR: Unknown audit reservation.")

            reservation = cls._pending.pop(reservation_id)

            event_payload = {
                "schema_version": "AUDIT-V1",
                "reservation_id": reservation_id,
                "event_type": reservation["event_type"],
                "status": status,
                "original_payload": reservation["payload"],
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "previous_hash": cls._last_hash
            }

            # 1. Strict RFC8785 Serialization
            canonical_event = StrictCryptographicEngine.rfc8785_canonical_serialize(event_payload)
            
            # 2. Strict Context-Bound Digest (AUDIT context)
            current_hash_bytes = StrictCryptographicEngine.compute_signing_digest(
                message=canonical_event,
                context="AUDIT"
            )
            current_hash = current_hash_bytes.hex()

            record = {
                "previous_hash": cls._last_hash,
                "event_hash": current_hash,
                "event": event_payload
            }

            cls._append_record(record)

            cls._last_hash = current_hash
            cls._events_since_anchor += 1

            if cls._events_since_anchor >= cls.ANCHOR_INTERVAL:
                cls._anchor_chain()

    @classmethod
    def _append_record(cls, record: Dict[str, Any]) -> None:
        directory = os.path.dirname(cls.LOG_FILE)
        if directory:
            os.makedirs(directory, exist_ok=True)

        # Enforce fail-closed logging
        try:
            with open(cls.LOG_FILE, "a") as f:
                f.write(json.dumps(record, separators=(",", ":")) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Audit log write failed: {e}")

    @classmethod
    def _write_raw(cls, data: Dict[str, Any]) -> None:
        cls._append_record(data)

    @classmethod
    def _anchor_chain(cls) -> None:
        """
        Anchors current chain state into KMS to prevent historical erasure.
        """
        try:
            kms = AWSKMSProvider()
            digest = StrictCryptographicEngine.sha384_digest(cls._last_hash.encode("utf-8"))

            kms.sign_digest(
                key_id=os.environ["TE_AUDIT_KMS_KEY_ARN"],
                digest=digest,
                purpose="AUDIT",
                certificate_serial="AUDIT_ANCHOR"
            )
            
            cls._events_since_anchor = 0
        except Exception as e:
            raise RuntimeError(f"CRITICAL SECURITY ERROR: Audit anchoring failed: {e}")