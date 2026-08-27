# research/falsification/harness.py
from research.falsification.theorem_engine import FalsificationEngine
# ... existing imports ...

class FalsificationHarness:
    def __init__(self):
        self.falsification_engine = FalsificationEngine()

    def run_suite(self, raw_data):
        # Baseline check
        baseline_cert = self.falsification_engine.verify(tracked_signals.node)
        
        # Negative control check
        cert = self.falsification_engine.verify(
            control(TrackedDataFrame(raw_data)).node
        )
        
        # Corrupted signal check
        cert = self.falsification_engine.verify(
            corrupted_signals.node
        )
        return cert