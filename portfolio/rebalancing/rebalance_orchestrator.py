from contracts.signal_validation import SignalValidationResult
from contracts.risk_constraints import RiskConstraints
from typing import List
from typing import Dict, Any, List
from portfolio.rebalancing.drift_monitor import DriftMonitor
from portfolio.rebalancing.constraint_engine import ConstraintEngine
from portfolio.rebalancing.trade_generator import TradeGenerator
from portfolio.rebalancing.cash_allocator import CashAllocator
from portfolio.rebalancing.turnover_optimizer import TurnoverOptimizer

class PortfolioDecisionPipeline:
    """
    Centralized orchestration engine coordinating validation, optimization, 
    risk, capacity, execution simulation, and rebalancing into a single production workflow.
    """
    
    def __init__(self, nav: float, current_weights: Dict[str, float], current_prices: Dict[str, float], available_cash: float):
        self.nav = nav
        self.current_weights = current_weights
        self.prices = current_prices
        self.cash = available_cash
        
        self.constraint_engine = ConstraintEngine()
        self.cash_allocator = CashAllocator()
        self.turnover_optimizer = TurnoverOptimizer()

    def execute_rebalance_cycle(
        self,
        validated_signals: List[SignalValidationResult],
        risk_constraints: RiskConstraints,
        market_data_map: Dict[str, Dict[str, float]]
    ) -> Dict[str, Any]:
        # 1. Enforce hard portfolio constraints on target weights
        cash_pct = self.cash / self.nav
        constraint_check = self.constraint_engine.validate_constraints(target_weights, cash_pct)
        if not constraint_check["passed"]:
            return {"status": "REJECTED", "reason": "Constraint violation", "details": constraint_check["violations"]}

        # 2. Check portfolio drift
        drift_monitor = DriftMonitor(target_weights)
        drift_status = drift_monitor.check_drift(self.current_weights)
        if not drift_status["needs_rebalance"]:
            return {"status": "NO_ACTION", "reason": "Portfolio drift within acceptable tolerance."}

        # 3. Generate raw trades
        trade_gen = TradeGenerator(self.nav, self.prices)
        raw_trades = trade_gen.generate_trades(self.current_weights, target_weights)

        # 4. Allocate cash constraints
        cash_adjusted_trades = self.cash_allocator.allocate_cash(raw_trades, self.cash)

        # 5. Optimize turnover / suppress friction
        optimized_trades = self.turnover_optimizer.filter_insignificant_trades(cash_adjusted_trades)

        # 6. Simulate institutional execution on optimized trades
        execution_results = []
        for t in optimized_trades:
            mdata = market_data_map.get(t["symbol"], {"spread": 0.001, "volatility": 0.20, "adv": 1000000})
            order = Order(symbol=t["symbol"], side=t["side"], quantity=t["quantity"])
            sim = ExecutionSimulator(
                arrival_price=self.prices.get(t["symbol"], 100.0),
                spread=mdata["spread"],
                volatility=mdata["volatility"],
                adv_shares=mdata["adv"]
            )
            res = sim.simulate_execution(order)
            execution_results.append(res)

        return {
            "status": "APPROVED",
            "drift_summary": drift_status,
            "optimized_trades_count": len(optimized_trades),
            "execution_simulations": execution_results
        }
