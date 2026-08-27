import unittest
from research.scanner.momentum_scanner import MomentumScanner
from research.promotion.engine import ResearchPromotionEngine
from research.promotion.threshold_policy import InstitutionalThresholdPolicy
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
from .invariants import STRUCTURAL_INVARIANTS

class PromotedResearchScannerComponent:
    """VSC Stage component integrating the Research Promotion Policy Engine."""
    def __init__(self, engine=None, factory=None):
        self.scanner = MomentumScanner()
        self.engine = engine or ResearchPromotionEngine()
        self.factory = factory or ResearchSignalFactory()

    def transform(self, context: PipelineContext):
        candidates = self.scanner.scan()
        
        # Execute promotion audit
        decisions = self.engine.filter_and_promote(candidates)
        print("\n--- Research Promotion Audit Log ---")
        for d in decisions:
            status = "PROMOTED ✅" if d.is_promoted else "REJECTED ❌"
            print(f"[{status}] Symbol: {d.candidate.symbol} | Rationale: {'; '.join(d.reasons)}")
        print("-" * 38)

        # Select top promoted candidate
        top_promoted = self.engine.get_top_promoted(candidates)
        return self.factory.create(top_promoted, context.root_contract_id, context.correlation_id)

class TestVSC2_1PromotionFlow(unittest.TestCase):

    def test_promotion_engine_filtering_and_pipeline(self):
        print("\n==================================================")
        print(" Starting VSC 2.1 Research Promotion Flow Test")
        print("==================================================")

        pipeline = VSCPipeline(
            research_gen=PromotedResearchScannerComponent(),
            governance=GovernanceComponent(),
            intent_stage=PortfolioIntentComponent(),
            risk_stage=PortfolioRiskComponent(),
            planning_stage=ExecutionPlanningComponent(),
            broker_stage=BrokerExecutionComponent(),
            feedback_stage=FeedbackComponent()
        )

        pipeline_result = pipeline.run()
        contracts = pipeline_result.contracts
        signal, approved, intent, decision, plan, result, feedback = contracts

        # 1. Verify NVDA was promoted and selected (AAPL fails due to confidence 0.82 < 0.85 default threshold)
        self.assertEqual(signal.symbol, "NVDA")
        self.assertEqual(signal.confidence_score, 0.89)

        # 2. Structural invariants verification
        self.assertEqual(len(contracts), STRUCTURAL_INVARIANTS["chain_length"])

        print("\n==================================================")
        print(" 🎉 VSC 2.1 Research Promotion Policy Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
