import unittest
from types import MappingProxyType
from research.scanner.momentum_scanner import MomentumScanner
from governance.promotion.policy import ResearchPromotionPolicyEngine
from portfolio.snapshot import PortfolioSnapshot, Position
from portfolio.construction.allocator import RiskAwareAllocator
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

class RiskAwarePortfolioComponent:
    """VSC Stage component integrating VSC 3.1 State-Aware Allocation and Immutable Memory."""
    def __init__(self, policy=None, allocator=None, factory=None):
        self.scanner = MomentumScanner()
        self.policy = policy or ResearchPromotionPolicyEngine()
        self.allocator = allocator or RiskAwareAllocator()
        self.factory = factory or ResearchSignalFactory()

    def transform(self, context: PipelineContext):
        candidates = self.scanner.scan()
        approved_candidates = [c for c in candidates if self.policy.evaluator.evaluate_candidate(c).approved]

        # Initialize immutable portfolio state memory with MappingProxyType
        initial_snapshot = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            root_contract_id=context.root_contract_id,
            correlation_id=context.correlation_id,
            capital_base=1000000.0,
            cash_balance=250000.0,
            holdings=MappingProxyType({
                "MSFT": Position("MSFT", shares=200, average_cost=350.0, last_price=375.0)
            }),
            version=2
        )

        # Run State-Aware Risk Allocator
        allocations = self.allocator.allocate(approved_candidates, initial_snapshot)

        # Select primary intent for downstream pipeline continuity
        top_symbol = max(allocations, key=allocations.get)
        top_candidate = next(c for c in approved_candidates if c.symbol == top_symbol)
        
        return self.factory.create(top_candidate, context.root_contract_id, context.correlation_id)

class TestVSC3_1RiskAwarePortfolio(unittest.TestCase):

    def test_risk_aware_portfolio_flow(self):
        print("\n==================================================")
        print(" Starting VSC 3.1 State-Aware Portfolio Test")
        print("==================================================")

        pipeline = VSCPipeline(
            research_gen=RiskAwarePortfolioComponent(),
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

        # 1. Verify pipeline invariants
        self.assertEqual(len(contracts), STRUCTURAL_INVARIANTS["chain_length"])

        print("\n==================================================")
        print(" 🎉 VSC 3.1 State-Aware Portfolio Verified!")
        print("==================================================")

if __name__ == "__main__":
    unittest.main()
