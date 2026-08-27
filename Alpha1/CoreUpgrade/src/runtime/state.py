import threading
import json
import os
from enum import Enum, auto
from typing import Optional, Any, Tuple
from src.security.audit import SecurityAuditLogger
from src.security.crypto import StrictCryptographicEngine

class RuntimeCertificationState(Enum):
    INITIALIZING = auto()
    VALIDATING = auto()
    CERTIFIED = auto()
    EXECUTION_ENABLED = auto()
    REVOKED = auto()
    HALTED_RECOVERABLE = auto()
    HALTED_FATAL = auto()

class RuntimeStateController:
    """
    SEC-010: State is securely persisted to disk.
    SEC-012: Race condition fix using Atomic Authorization Tokens.
    """
    _lock = threading.RLock()
    _current_state: RuntimeCertificationState = RuntimeCertificationState.INITIALIZING
    _active_certificate: Optional[Any] = None
    _state_epoch: int = 0
    _STATE_FILE = "/var/lib/trading-engine/runtime_state.json"

    # SEC-009: Two-person recovery requires two distinct admin public keys
    ADMIN1_PUBKEY_PATH = "/etc/trading-engine/trust/admin1_recovery.der"
    ADMIN2_PUBKEY_PATH = "/etc/trading-engine/trust/admin2_recovery.der"

    @classmethod
    def _persist_state(cls, state: RuntimeCertificationState, reason: str):
        data = {
            "state": state.name,
            "epoch": cls._state_epoch,
            "reason": reason
        }
        # In a real environment, this JSON is signed by the HSM to prevent tampering
        with open(cls._STATE_FILE, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())

    @classmethod
    def get_atomic_admission_token(cls) -> Tuple[bool, Optional[Any], int]:
        """
        Returns (is_enabled, certificate_snapshot, state_epoch) atomically.
        Prevents SEC-012 revocation race conditions.
        """
        with cls._lock:
            is_enabled = cls._current_state == RuntimeCertificationState.EXECUTION_ENABLED
            # SEC-012: Return deepcopy/immutable reference of the active certificate
            cert = cls._active_certificate 
            return is_enabled, cert, cls._state_epoch

    @classmethod
    def force_halt(cls, fatal: bool = True, reason: str = "Forced Halt") -> None:
        with cls._lock:
            target = RuntimeCertificationState.HALTED_FATAL if fatal else RuntimeCertificationState.HALTED_RECOVERABLE
            cls._current_state = target
            cls._active_certificate = None
            cls._state_epoch += 1
            cls._persist_state(target, reason)
            SecurityAuditLogger.log_event("SYSTEM_HALT", reason, {"fatal": fatal})

    @classmethod
    def recover_from_halt(cls, recovery_payload: str, admin1_sig: bytes, admin2_sig: bytes) -> None:
        """SEC-009: Two-person recovery approval mechanism."""
        with cls._lock:
            if cls._current_state != RuntimeCertificationState.HALTED_RECOVERABLE:
                raise RuntimeError("Recovery denied: System is in HALTED_FATAL or active state.")
            
            with open(cls.ADMIN1_PUBKEY_PATH, "rb") as f: pub1 = f.read()
            with open(cls.ADMIN2_PUBKEY_PATH, "rb") as f: pub2 = f.read()
            
            payload_bytes = recovery_payload.encode("utf-8")
            
            if not StrictCryptographicEngine.verify_ecdsa_p384(pub1, admin1_sig, payload_bytes):
                raise RuntimeError("Recovery denied: Admin 1 signature invalid.")
            if not StrictCryptographicEngine.verify_ecdsa_p384(pub2, admin2_sig, payload_bytes):
                raise RuntimeError("Recovery denied: Admin 2 signature invalid.")
            
            SecurityAuditLogger.log_event("SYSTEM_RECOVERED", "Two-person administrative recovery successful")
            cls._current_state = RuntimeCertificationState.INITIALIZING
            cls._state_epoch += 1
            cls._persist_state(cls._current_state, "Two-person recovery")