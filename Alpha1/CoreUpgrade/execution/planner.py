from contracts.execution_decision import ExecutionDecisionContract
from execution.cost_model import ExecutionCostModel
from execution.strategies import ExecutionStrategySelector

class ExecutionIntelligenceEngine:
    """Optimizes execution strategy and estimates slippage based on portfolio risk and market ADV."""

    def plan_execution(self, risk_contract, target_orders, market_adv_map=None):
        decisions = []
        market_adv_map = market_adv_map or {"NVDA": 2000000.0, "MSFT": 5000000.0}

        for symbol, order_info in target_orders.items():
            side = order_info.get("side", "BUY")
            qty = order_info.get("quantity", 100.0)
            price = order_info.get("price", 100.0)
            order_value = qty * price

            adv = market_adv_map.get(symbol, 1000000.0)
            costs = ExecutionCostModel.estimate_costs(order_value, qty, adv=adv, volatility=risk_contract.volatility)
            
            strategy = ExecutionStrategySelector.select_strategy(costs["participation_rate"])

            decision = ExecutionDecisionContract(
                root_contract_id=risk_contract.root_contract_id,
                correlation_id=risk_contract.correlation_id,
                parent_contract_id=risk_contract.immutable_id,
                portfolio_id=risk_contract.portfolio_id,
                parent_risk_id=risk_contract.immutable_id,
                symbol=symbol,
                side=side,
                quantity=qty,
                selected_strategy=strategy,
                expected_spread_cost=costs["spread_cost"],
                market_impact=costs["market_impact"],
                estimated_slippage=costs["estimated_slippage"],
                urgency="MEDIUM",
                execution_status="OPTIMIZED"
            )
            decisions.append(decision)

        return decisions
