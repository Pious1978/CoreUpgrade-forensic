import unittest
from research.scanner.momentum_scanner import MomentumScanner
from research.factory import ResearchSignalFactory
from governance.promotion.policy import ResearchPromotionPolicyEngine
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

class MultiFactorGovernedScannerComponent:
    """VSC Stage component integrating VSC 2.2 Multi-Factor Governance."""
    def __init__(self, policy=None, factory=None):
        self.scanner = MomentumScanner()
        self.policy = policy or ResearchPromotionPolicyEngine()
        self.factory = factory or ResearchSignalFactory()

    def transform(self, context: PipelineContext):
        candidates = self.scanner.scan()
        top_candidate = self.policy.select_best_promoted(candidates)
        return self.factory.create(top_candidate, context.root_contract_id, context.correlation_id)

class TestVSC2_2MultiFactorGovernance(unittest.TestCase):

    def test_multi_factor_governance_flow(self):
        print("\n==================================================")
        print(" Starting VSC 2.2 Multi-Factor Governance Test")
        print("==================================================")

        pipeline = VSCPipeline(
            research_gen=MultiFactorGovernedScannerComponent(),
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

        # 1. Verify NVDA successfully navigated all multi-factor gates
        self.assertEqual(signal.symbol, "NVDA")
        self.assertEqual(signal.confidence_score, 0.89)

        # 2. Verify structural invariants
        self.assertEqual(len(contracts), STRUCTURAL_INVARIANTS["chain_length"])

        print("\n==================================================")
        print(" 🎉 VSC 2.2 Multi-Factor Governance Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
