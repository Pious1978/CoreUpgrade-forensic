# portfolio/engines/rebalance_orchestration_service.py

from datetime import datetime
from decimal import Decimal

from portfolio.contracts.portfolio_contract import PortfolioContract
from portfolio.contracts.holdings_snapshot_contract import HoldingsSnapshotContract
from portfolio.contracts.portfolio_certificate import PortfolioCertificate
from portfolio.engines.rebalance_engine import RebalanceEngine

from execution.translation.portfolio_to_execution import (
    translate_rebalance_to_intent,
)
from execution.translation.execution_to_oms import (
    translate_intent_to_oms_order,
)

from oms.contracts.order_intent import (
    OrderIntentContract,
    OrderType,
)


class RebalanceOrchestrationService:
    """
    Canonical orchestration boundary for portfolio rebalance execution.

    Translation spine:

        PortfolioContract
            ↓
        RebalanceEngine
            ↓
        RebalanceInstructionContract
            ↓
        ExecutionIntent
            ↓
        OrderIntentContract

    This service is responsible only for portfolio-to-OMS intent
    construction.

    It does not construct RiskCheckRequest objects.
    It does not perform risk evaluation.
    It does not submit orders to the OMS.
    It does not execute brokers.

    Those responsibilities remain in their canonical layers.
    """

    def __init__(
        self,
        rebalance_engine: RebalanceEngine | None = None,
    ) -> None:
        self.rebalance_engine = (
            rebalance_engine
            if rebalance_engine is not None
            else RebalanceEngine()
        )

    def build_oms_orders(
        self,
        portfolio_contract: PortfolioContract,
        holdings_snapshot: HoldingsSnapshotContract,
        certificate: PortfolioCertificate,
        *,
        execution_policy_id: str,
        urgency: str,
        timestamp: datetime,
        strategy_id: str,
        currency: str,
        order_type: OrderType = OrderType.MARKET,
        risk_request_id: str,
        price: Decimal | None = None,
    ) -> tuple[OrderIntentContract, ...]:
        """
        Build canonical OMS OrderIntentContract objects.

        Flow:

            PortfolioContract
                ↓
            RebalanceEngine
                ↓
            RebalanceInstructionContract
                ↓
            ExecutionIntent
                ↓
            OrderIntentContract

        No risk evaluation, OMS submission, or broker execution occurs here.
        """

        instructions = self.rebalance_engine.generate_instructions(
            portfolio_contract=portfolio_contract,
            holdings_snapshot=holdings_snapshot,
        )

        oms_orders: list[OrderIntentContract] = []

        for instruction in instructions:

            execution_intent = translate_rebalance_to_intent(
                instruction=instruction,
                certificate=certificate,
                execution_policy_id=execution_policy_id,
                urgency=urgency,
                timestamp=timestamp,
            )

            oms_order = translate_intent_to_oms_order(
                intent=execution_intent,
                strategy_id=strategy_id,
                currency=currency,
                order_type=order_type,
                risk_request_id=risk_request_id,
                timestamp=timestamp,
                price=price,
            )

            oms_orders.append(oms_order)

        return tuple(oms_orders)