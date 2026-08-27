"""
Thread-Safe Runtime State Controller & Administrative Reset

Authority:
    Execution Layer State Machine, Mutability Lock & Admin Reset Governance
"""
import threading
from enum import Enum
from typing import Any

class RuntimeCertificationState(Enum):
    INITIALIZING = "INITIALIZING"
    VALIDATING = "VALIDATING"
    CERTIFIED = "CERTIFIED"
    EXECUTION_ENABLED = "EXECUTION_ENABLED"
    HALTED = "HALTED"
    REVOKED = "REVOKED"

class RuntimeStateController:
    _state = RuntimeCertificationState.INITIALIZING
    _lock = threading.Lock()
    _active_certificate = None

    @classmethod
    def transition(cls, target_state: RuntimeCertificationState):
        with cls._lock:
            valid_transitions = {
                RuntimeCertificationState.INITIALIZING: [RuntimeCertificationState.VALIDATING, RuntimeCertificationState.HALTED],
                RuntimeCertificationState.VALIDATING: [RuntimeCertificationState.CERTIFIED, RuntimeCertificationState.HALTED],
                RuntimeCertificationState.CERTIFIED: [RuntimeCertificationState.EXECUTION_ENABLED, RuntimeCertificationState.REVOKED, RuntimeCertificationState.HALTED],
                RuntimeCertificationState.EXECUTION_ENABLED: [RuntimeCertificationState.HALTED, RuntimeCertificationState.REVOKED],
                RuntimeCertificationState.HALTED: [RuntimeCertificationState.INITIALIZING],
                RuntimeCertificationState.REVOKED: []
            }
            if target_state not in valid_transitions.get(cls._state, []):
                raise RuntimeError(f"Invalid thread-safe state transition: {cls._state.value} -> {target_state.value}")
            cls._state = target_state

    @classmethod
    def get_state(cls) -> RuntimeCertificationState:
        with cls._lock:
            return cls._state

    @classmethod
    def set_active_certificate(cls, certificate: Any):
        with cls._lock:
            cls._active_certificate = certificate

    @classmethod
    def get_active_certificate(cls) -> Any:
        with cls._lock:
            return cls._active_certificate

    @classmethod
    def assert_execution_enabled(cls):
        with cls._lock:
            if cls._state != RuntimeCertificationState.EXECUTION_ENABLED:
                raise RuntimeError(f"Security Violation: Engine state is {cls._state.value}, not EXECUTION_ENABLED.")
```[cite: 37]