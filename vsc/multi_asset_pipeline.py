from dataclasses import dataclass, field
from typing import List, Mapping
from uuid import uuid4, UUID
from types import MappingProxyType

from research.scanner.momentum_scanner import MomentumScanner
from governance.promotion.policy import ResearchPromotionPolicyEngine
from portfolio.snapshot import PortfolioSnapshot, Position
from portfolio.construction.allocator import RiskAwareAllocator
from research.factory import ResearchSignalFactory
from .invariants import TrustLevel, LifecycleState

@dataclass(frozen=True)
class MultiAssetPipelineResult:
    contracts: list
    telemetry: object

class MultiAssetVSCPipeline:
    """Orchestrator for native multi-asset portfolio intent, risk, planning, and execution."""
    def __init__(self, allocator=None, policy=None):
        self.allocator = allocator or RiskAwareAllocator()
        self.policy = policy or ResearchPromotionPolicyEngine()

    def run(self) -> MultiAssetPipelineResult:
        root_id = uuid4()
        correlation_id = uuid4()

        # 1. Research & Governance Stage
        scanner = MomentumScanner()
        candidates = scanner.scan()
        approved_candidates = [c for c in candidates if self.policy.evaluator.evaluate_candidate(c).approved]

        # 2. Portfolio State & State-Aware Allocation
        snapshot = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            root_contract_id=root_id,
            correlation_id=correlation_id,
            capital_base=1000000.0,
            cash_balance=250000.0,
            holdings=MappingProxyType({
                "MSFT": Position("MSFT", shares=200, average_cost=350.0, last_price=375.0)
            }),
            version=2
        )

        allocations = self.allocator.allocate(approved_candidates, snapshot)

        print("\n--- VSC 3.5 Multi-Asset Pipeline Execution ---")
        print(f"Root Contract ID: {str(root_id)[:8]}... | Correlation ID: {str(correlation_id)[:8]}...")
        print("Basket Allocations successfully locked across approved universe.")
        print("-" * 52)

        return MultiAssetPipelineResult(
            contracts=[approved_candidates, allocations, snapshot],
            telemetry=None
        )
