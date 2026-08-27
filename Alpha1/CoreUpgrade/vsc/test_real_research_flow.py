import unittest
from dataclasses import FrozenInstanceError
from research.scanner.momentum_scanner import MomentumScanner
from research.ranking.signal_ranker import SignalRanker
from research.factory import ResearchSignalFactory
from .pipeline import (
    VSCPipeline,
    PipelineContext,
    GovernanceComponent,
    PortfolioIntentComponent,
    PortfolioRiskComponent,
    ExecutionPlanningComponent,
    BrokerExecutionComponent,
    FeedbackComponent,
)
from .invariants import (
    STRUCTURAL_INVARIANTS,
    BUSINESS_INVARIANTS,
    TrustLevel,
    LifecycleState,
)

class ResearchScannerComponent:
    """Adapter component bridging the real research ecosystem into the VSC pipeline."""
    def __init__(self, scanner=None, ranker=None, factory=None):
        self.scanner = scanner or MomentumScanner()
        self.ranker = ranker or SignalRanker()
        self.factory = factory or ResearchSignalFactory()

    def transform(self, context: PipelineContext):
        candidates = self.scanner.scan()
        top_candidate = self.ranker.rank(candidates)
        return self.factory.create(top_candidate, context.root_contract_id, context.correlation_id)


class TestVSC2_0RealResearchFlow(unittest.TestCase):

    def test_real_research_end_to_end(self):
        print("\n==================================================")
        print(" Starting VSC 2.0 Real Research Integration Test")
        print("==================================================")

        # Inject real research components into the standard pipeline orchestrator
        pipeline = VSCPipeline(
            research_gen=ResearchScannerComponent(),  # <-- Real Research Scanner
            governance=GovernanceComponent(),
            intent_stage=PortfolioIntentComponent(),
            risk_stage=PortfolioRiskComponent(),
            planning_stage=ExecutionPlanningComponent(),
            broker_stage=BrokerExecutionComponent(),
            feedback_stage=FeedbackComponent()
        )
        
        pipeline_result = pipeline.run()
        contracts = pipeline_result.contracts
        telemetry = pipeline_result.telemetry
        signal, approved, intent, decision, plan, result, feedback = contracts

        # 1. Assert Real Research Output Sourced Correctly (NVDA selected over AAPL)
        self.assertEqual(signal.symbol, "NVDA")
        self.assertEqual(signal.confidence_score, 0.89)

        # 2. Verify Immutability
        with self.assertRaises(FrozenInstanceError):
            signal.symbol = "MSFT"

        # 3. Structural & Business Invariants Verification
        self.assertEqual(len(contracts), STRUCTURAL_INVARIANTS["chain_length"])

        visited_ids = set()
        for i, c in enumerate(contracts):
            self.assertNotIn(c.immutable_id, visited_ids)
            visited_ids.add(c.immutable_id)
            self.assertEqual(c.root_contract_id, signal.root_contract_id)
            self.assertEqual(c.correlation_id, signal.correlation_id)
            if i > 0:
                self.assertEqual(c.parent_contract_id, contracts[i-1].immutable_id)

        # Operational Telemetry Table
        print("\n--- VSC 2.0 Real Research Telemetry ---")
        print(f"{'Stage Name':<22} | {'Duration (ms)':<14} | {'Input Type':<20} | {'Output Contract':<28}")
        print("-" * 92)
        for m in telemetry.metrics:
            print(f"{m.stage_name:<22} | {m.duration_ms:<14.3f} | {m.input_type:<20} | {m.output_type:<28}")
        print("-" * 92)

        print("\n--- VSC 2.0 Real Research Contract Chain Visualization ---")
        for i, c in enumerate(contracts):
            indent = "  " * i
            print(f"{indent}└─► [{c.contract_type}] (Symbol: {getattr(c, 'symbol', 'N/A')}, ID: {str(c.immutable_id)[:8]}..., Trust: {c.trust_level})")
        print("----------------------------------------------------------")

        print("==================================================")
        print(" 🎉 VSC 2.0 Real Research Integration Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
