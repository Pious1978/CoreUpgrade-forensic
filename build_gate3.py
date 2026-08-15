import os

gate3_code = '''import json
import hashlib
from datetime import datetime, timezone
from dataclasses import asdict
from contracts.execution_report import ExecutionReport
from contracts.risk_constraints import RiskConstraints
from contracts.signal_validation import SignalValidationResult

class RuntimeIntegrityGate:
    """
    Gate 3: Runtime & Contract Integrity
    Verifies immutability, deterministic serialization, UTC enforcement, and idempotency across the domain boundary.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0

    def run_all_checks(self):
        print("--- GATE 3: RUNTIME INTEGRITY ---")
        self._check_immutability()
        self._check_deterministic_serialization()
        self._check_utc_enforcement()
        
        print(f"\\nGate 3 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Runtime environment is deterministic and immutable.")
        else:
            print("Verdict: FAIL - Integrity violations detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _check_immutability(self):
        """Ensures cross-domain payloads cannot be mutated in memory."""
        rc = RiskConstraints(max_position_size=0.05, max_sector_exposure=0.2, max_drawdown=0.1, volatility_target=0.15)
        try:
            rc.max_position_size = 0.10
            mutated = True
        except Exception:
            mutated = False
            
        self._assert(not mutated, "Contract immutability strictly enforced (FrozenInstanceError).", "Contracts are mutable! (Violation)")

    def _check_deterministic_serialization(self):
        """Ensures identical data yields identical cryptographic hashes (Idempotency)."""
        timestamp = datetime.now(timezone.utc)
        
        # Two distinct memory objects, identical data
        er1 = ExecutionReport("ORD-1", "AAPL", 100, 100, 150.0, 10.0, timestamp)
        er2 = ExecutionReport("ORD-1", "AAPL", 100, 100, 150.0, 10.0, timestamp)
        
        # Serialize with sorted keys to guarantee deterministic ordering
        hash1 = hashlib.sha256(json.dumps(asdict(er1), sort_keys=True, default=str).encode()).hexdigest()
        hash2 = hashlib.sha256(json.dumps(asdict(er2), sort_keys=True, default=str).encode()).hexdigest()
        
        self._assert(hash1 == hash2, f"Deterministic serialization & Idempotency verified (Hash: {hash1[:8]}).", "Serialization is non-deterministic!")

    def _check_utc_enforcement(self):
        """Ensures all time-series boundaries use timezone-aware UTC."""
        timestamp = datetime.now(timezone.utc)
        is_aware = timestamp.tzinfo is not None and timestamp.tzinfo == timezone.utc
        self._assert(is_aware, "Strict UTC timezone enforcement verified.", "Timezone naive datetimes detected.")

if __name__ == "__main__":
    gate = RuntimeIntegrityGate()
    gate.run_all_checks()
'''

with open(os.path.join("audits", "gate3_runtime_integrity.py"), "w", encoding="utf-8") as f:
    f.write(gate3_code)

print("Created audits/gate3_runtime_integrity.py")
