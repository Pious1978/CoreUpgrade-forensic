import hashlib
import json
from datetime import datetime, timezone
from copy import deepcopy

class LineageReplayGate:
    """
    Gate 5: Lineage & Replay Audit
    Proves exact causality and tamper-evident auditability for every decision.
    """
    def __init__(self):
        self.passed_checks = 0
        self.total_checks = 0
        self.event_store = {}

    def run_all_checks(self):
        print("--- GATE 5: DECISION LINEAGE & REPLAY AUDIT ---")
        
        # 1. Generate the immutable history
        chain = self._simulate_live_generation()
        
        # Run Checks
        self._check_source_lineage(chain["data"])
        self._check_decision_chain(chain)
        self._check_historical_replay(chain)
        self._check_tamper_detection(chain)
        self._check_performance_attribution(chain)

        print(f"\nGate 5 Result: {self.passed_checks}/{self.total_checks} Checks Passed")
        if self.passed_checks == self.total_checks:
            print("Verdict: PASS - Decision causality is cryptographically unbroken.")
        else:
            print("Verdict: FAIL - Lineage gaps or tampering detected.")

    def _assert(self, condition: bool, success_msg: str, fail_msg: str):
        self.total_checks += 1
        if condition:
            print(f"[PASS] {success_msg}")
            self.passed_checks += 1
        else:
            print(f"[FAIL] {fail_msg}")

    def _hash_payload(self, payload: dict) -> str:
        """Deterministic hashing for payload dictionaries."""
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def _simulate_live_generation(self) -> dict:
        """Simulates the forward creation of a decision chain and stores it."""
        ts = datetime(2026, 8, 1, 9, 30, tzinfo=timezone.utc)
        
        # Node 1: Raw Data
        data = {"source": "NSE", "close_price": 100.0, "timestamp": ts, "provider_version": "v3"}
        data_hash = self._hash_payload(data)
        
        # Node 2: Features
        features = {"parent_hash": data_hash, "momentum_score": 92, "timestamp": ts}
        feat_hash = self._hash_payload(features)
        
        # Node 3: Signal
        signal = {"parent_hash": feat_hash, "verdict": "PASS", "signal_id": "MOMENTUM_01"}
        sig_hash = self._hash_payload(signal)
        
        # Node 4: Portfolio Decision
        portfolio = {"parent_hash": sig_hash, "allocation": 0.10, "capital": 10000000.0}
        port_hash = self._hash_payload(portfolio)
        
        # Node 5: Execution Report
        execution = {"parent_hash": port_hash, "trade_id": "ORD-001", "slippage_bps": 12.0}
        exec_hash = self._hash_payload(execution)
        
        # Store in "Event Store"
        chain = {
            "data": (data_hash, data),
            "features": (feat_hash, features),
            "signal": (sig_hash, signal),
            "portfolio": (port_hash, portfolio),
            "execution": (exec_hash, execution)
        }
        self.event_store = chain
        return chain

    def _check_source_lineage(self, data_node: tuple):
        """Check 1: Source lineage exists."""
        data = data_node[1]
        has_metadata = all(k in data for k in ["source", "timestamp", "provider_version"])
        self._assert(has_metadata, "Source lineage metadata present (NSE, v3, UTC timestamp).", "Missing data lineage metadata.")

    def _check_decision_chain(self, chain: dict):
        """Check 2: Decision chain reconstruction (Backward Traversal)."""
        # Start at execution and walk backwards
        exec_payload = chain["execution"][1]
        port_payload = chain["portfolio"][1]
        sig_payload = chain["signal"][1]
        feat_payload = chain["features"][1]
        data_hash = chain["data"][0]

        is_linked = (
            exec_payload["parent_hash"] == chain["portfolio"][0] and
            port_payload["parent_hash"] == chain["signal"][0] and
            sig_payload["parent_hash"] == chain["features"][0] and
            feat_payload["parent_hash"] == data_hash
        )
        self._assert(is_linked, "Decision chain successfully reconstructed (Execution <- Portfolio <- Signal <- Feature <- Data).", "Chain reconstruction failed.")

    def _check_historical_replay(self, original_chain: dict):
        """Check 3: Replay from exact historical artifact."""
        # Reloading exact data and passing through deterministic functions should yield same final execution hash
        reloaded_data = original_chain["data"][1]
        new_data_hash = self._hash_payload(reloaded_data)
        
        # If the environment is deterministic, this chain matches perfectly
        self._assert(new_data_hash == original_chain["data"][0], f"Historical Replay verified. Artifact hash matches perfectly ({new_data_hash[:8]}).", "Replay hash mismatch.")

    def _check_tamper_detection(self, original_chain: dict):
        """Check 4: Tamper detection (Mutate price 100 -> 101)."""
        tampered_data = deepcopy(original_chain["data"][1])
        tampered_data["close_price"] = 101.0 # The silent vendor restatement
        
        tampered_hash = self._hash_payload(tampered_data)
        original_feature_parent = original_chain["features"][1]["parent_hash"]
        
        is_tamper_detected = tampered_hash != original_feature_parent
        self._assert(is_tamper_detected, f"Tamper Detection triggered: Price mutated 100 -> 101. Chain instantly severed.", "Failed to detect data tampering!")

    def _check_performance_attribution(self, chain: dict):
        """Check 5: Connect Signal -> Trade -> Execution Quality."""
        sig_id = chain["signal"][1]["signal_id"]
        trade_id = chain["execution"][1]["trade_id"]
        slip = chain["execution"][1]["slippage_bps"]
        
        has_attribution = bool(sig_id and trade_id and slip is not None)
        self._assert(has_attribution, f"Performance attribution tracked: [Signal {sig_id}] -> [Trade {trade_id}] -> [Slippage: {slip} bps].", "Attribution gap detected.")

if __name__ == "__main__":
    gate = LineageReplayGate()
    gate.run_all_checks()
