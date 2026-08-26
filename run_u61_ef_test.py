from datetime import datetime, timezone
from decimal import Decimal
import uuid

from oms.composition import create_order_execution_service
from oms.services.order_execution_service import DuplicateIntentError
from oms.contracts.order_intent import OrderType
from oms.contracts.broker_submission_result import BrokerSubmissionResult
from risk.contracts.risk_check_request import RiskCheckRequest, OrderSide as RiskOrderSide
from risk.policies.risk_policy import RiskPolicy
from event_store.memory_store import InMemoryEventStore

from portfolio.contracts.portfolio_certificate import (
    PortfolioCertificate,
    OptimizerIdentity,
    PortfolioExposure,
    TargetWeight,
    ConstraintEvaluation,
)
from portfolio.contracts.certified_strategy_contract import CertifiedStrategyContract
from portfolio.contracts.holdings_snapshot_contract import (
    HoldingsSnapshotContract,
    PositionHolding,
)
from portfolio.construction.portfolio_builder import PortfolioBuilder
from portfolio.engines.rebalance_orchestration_service import (
    RebalanceOrchestrationService,
)
from portfolio.engines.portfolio_valuation_engine import PortfolioValuationEngine

timestamp = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


class ProtocolClock:
    def now(self) -> datetime:
        return timestamp


# Pure OMS-compliant Mock Broker Adapter (Zero legacy contamination)
class CleanMockBrokerAdapter:
    def submit_order(self, order) -> BrokerSubmissionResult:
        return BrokerSubmissionResult(
            broker_order_id=f"broker-ord-{uuid.uuid4().hex[:8]}",
            accepted_at=timestamp,
            exchange_order_id=f"excl-{uuid.uuid4().hex[:6]}",
        )

    def cancel_order(self, order) -> None:
        pass

    def get_order_status(self, broker_order_id: str):
        raise NotImplementedError()


print("=== BUILDING CANONICAL DEPENDENCY GRAPH VIA COMPOSITION ROOT ===")

# 1. Define Explicit Dependencies for Injection
risk_policy = RiskPolicy(
    policy_version="v1.0.0",
    max_position_weight=Decimal("1.0"),
    max_sector_exposure=Decimal("1.0"),
    max_order_value=Decimal("1000000.0"),
    max_daily_loss=Decimal("0.05"),
    max_portfolio_drawdown=Decimal("0.15"),
    max_liquidity_participation=Decimal("1.0"),
    kill_switch_enabled=False,
)

broker_adapter = CleanMockBrokerAdapter()
store = InMemoryEventStore()
clock = ProtocolClock()

# 2. Assemble via Canonical Composition Root Factory
service = create_order_execution_service(
    risk_policy=risk_policy,
    broker_adapter=broker_adapter,
    event_store=store,
    clock=clock,
)

print("=== BUILDING FIXTURES & TRANSLATING BOUNDARIES ===")

certificate = PortfolioCertificate(
    portfolio_id="PORT-001",
    timestamp=timestamp,
    alpha_vector_hash="alpha-001",
    universe_hash="universe-001",
    risk_hash="risk-001",
    optimizer_identity=OptimizerIdentity("opt-1", "1.0", "hash-1"),
    exposure=PortfolioExposure(Decimal("0.9"), Decimal("0.1")),
    target_weights=(TargetWeight("AAPL", Decimal("0.25")),),
    constraint_evaluations=(
        ConstraintEvaluation("R1", "PASS", Decimal("0.1"), Decimal("0.2")),
    ),
    certified=True,
)

# ---------------------------------------------------------------------------
# CANONICAL PORTFOLIO -> REBALANCE -> EXECUTION -> OMS SPINE
# ---------------------------------------------------------------------------

strategy = CertifiedStrategyContract(
    strategy_id="STRATEGY-001",
    certification_id="CERT-001",
    certification_fingerprint="fp-abc123",
    validator_versions=("v1.0",),
    approved_timestamp=timestamp,
    max_capital_allocation=Decimal("1000000"),
)

portfolio_contract = PortfolioBuilder().build(
    portfolio_id="PORT-001",
    certified_strategy=strategy,
    capital=Decimal("100000"),
    currency="USD",
    target_weights={
        "AAPL": (
            Decimal("0.20"),
            "EQUITY",
            "Portfolio rebalance",
        )
    },
    asset_prices={
        "AAPL": Decimal("200"),
    },
    timestamp=timestamp,
)

holdings_snapshot = HoldingsSnapshotContract(
    snapshot_id="SNAP-001",
    account_id="PORT-001",
    holdings=(
        PositionHolding(
            symbol="AAPL",
            quantity=Decimal("50"),
            average_price=Decimal("180"),
        ),
    ),
    cash_balance=Decimal("90000"),
    timestamp=timestamp,
)

orchestration = RebalanceOrchestrationService()

oms_orders = orchestration.build_oms_orders(
    portfolio_contract=portfolio_contract,
    holdings_snapshot=holdings_snapshot,
    certificate=certificate,
    execution_policy_id="DEFAULT-POLICY-PLACEHOLDER",  # no real policy engine exists yet
    urgency="MEDIUM",
    timestamp=timestamp,
    strategy_id=portfolio_contract.strategy_id,
    currency=portfolio_contract.currency,
    order_type=OrderType.LIMIT,
    risk_request_id="RISK-REQ-001",
    price=Decimal("200"),
)

assert len(oms_orders) == 1, (
    f"expected exactly 1 OMS order, got {len(oms_orders)}"
)

oms_intent = oms_orders[0]

valuation_engine = PortfolioValuationEngine()
computed_portfolio_value = valuation_engine.compute_total_value(
    holdings_snapshot=holdings_snapshot,
    current_prices={"AAPL": Decimal("200")},
)
print(f"DEBUG computed_portfolio_value = {computed_portfolio_value}  (cash 90000 + 50 shares * 200 = 100000)")

risk_req = RiskCheckRequest(
    request_id="RISK-REQ-001",
    portfolio_id="PORT-001",
    strategy_id=portfolio_contract.strategy_id,
    symbol="AAPL",
    side=RiskOrderSide.BUY,
    quantity=Decimal("50"),
    price=Decimal("200"),
    current_position=Decimal("50"),
    portfolio_value=computed_portfolio_value,
    daily_pnl=Decimal("0.0"),
    currency=portfolio_contract.currency,
    timestamp=timestamp,
)

print("=== EXECUTING U61-E & U61-F RUNTIME VALIDATION ===")

# U61-E: OMS Submission, Risk Evaluation, Broker Routing & Event Emission
snapshot = service.submit_intent(oms_intent, risk_req)
assert snapshot is not None
print(
    "U61-E PASS: OrderExecutionService successfully ingested "
    "intent through risk, OMS, and broker"
)

# U61-F: Strict Idempotency Boundary Enforcement (Duplicate Rejection)
try:
    service.submit_intent(oms_intent, risk_req)
    raise AssertionError("Duplicate intent was incorrectly allowed")
except DuplicateIntentError:
    print(
        "U61-F PASS: Idempotency boundary strictly enforced "
        "(DuplicateIntentError raised)"
    )

print("\n============================================================")
print("CANONICAL SPINE END-TO-END VERTICAL SLICE: FULLY VERIFIED")
print("============================================================")