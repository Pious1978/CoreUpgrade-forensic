# research/engine/backtest_engine.py
import pandas as pd
from research.data.tracked_dataframe import TrackedDataFrame
from research.certification.theorems.theorem_temporal_001 import CausalityTheorem

class BacktestEngine:
    def __init__(self, strategy):
        self.strategy = strategy

    def run(self, raw_market_data: pd.DataFrame) -> dict:
        tracked_data = TrackedDataFrame(raw_market_data)
        
        # Strategy executes completely oblivious to the tracing
        signals = self.strategy.generate_signals(tracked_data)
        
        # Extract the final Merkle-DAG node
        signal_graph = self.extract_feature_graph(signals)
        
        # Run Certification Gate
        cert_result = self.verify_theorem("THEOREM-TEMPORAL-001", signal_graph)
        
        if not cert_result["certified"]:
            return {
                "status": "FAILED_CERTIFICATION",
                "governance_report": cert_result["report"]
            }
            
        return {
            "status": "EXECUTION_COMPLETE",
            "simulated_trades": len(signals._s),
            "governance_report": cert_result["report"]
        }

    def extract_feature_graph(self, tracked_series):
        return tracked_series.node
        
    def verify_theorem(self, theorem_id, feature_graph):
        if theorem_id == CausalityTheorem.id:
            return CausalityTheorem.verify(feature_graph)
        raise ValueError(f"Unknown Theorem: {theorem_id}")
