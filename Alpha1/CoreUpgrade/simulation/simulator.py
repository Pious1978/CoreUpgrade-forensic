from types import MappingProxyType
from uuid import uuid4
import numpy as np
from portfolio.snapshot import PortfolioSnapshot, Position
from portfolio.accounting import PortfolioAccountingEngine
from risk.engine import PortfolioRiskEngine
from execution.planner import ExecutionIntelligenceEngine
from contracts.accounting import TradeFillContract

class ClosedLoopSimulator:
    """Orchestrates multi-period closed-loop simulation across risk, execution, accounting, and state mutation."""

    def __init__(self, initial_capital: float = 1000000.0):
        self.current_snapshot = PortfolioSnapshot(
            portfolio_id="PORTFOLIO-ALPHA-01",
            capital_base=initial_capital,
            cash_balance=initial_capital,
            holdings=MappingProxyType({}),
            version=1
        )
        self.accounting_engine = PortfolioAccountingEngine()
        self.risk_engine = PortfolioRiskEngine()
        self.execution_engine = ExecutionIntelligenceEngine()
        self.ledger_history = []
        self.snapshot_history = [self.current_snapshot]

    def step(self, target_orders: dict, market_data: dict) -> bool:
        """Executes a single simulation time-step tick."""
        print(f"\n--- Simulation Tick Start (Snapshot v{self.current_snapshot.version}) ---")
        
        # 1. Risk Evaluation Gateway
        risk_contract = self.risk_engine.evaluate(
            self.current_snapshot, 
            market_returns=market_data.get("returns")
        )
        
        if risk_contract.risk_status != "APPROVED":
            print(f"❌ Risk Gate BLOCKED execution. Status: {risk_contract.risk_status}")
            return False
        print(f"✅ Risk Gate APPROVED (Volatility: {risk_contract.volatility*100:.2f}%, VaR 95: ₹{risk_contract.var_95:,.2f})")

        # 2. Execution Intelligence & Cost Optimization
        execution_decisions = self.execution_engine.plan_execution(risk_contract, target_orders)

        # 3. Paper Execution & Accounting Ledger Mutation
        for decision in execution_decisions:
            fill_price = market_data.get("prices", {}).get(decision.symbol, 100.0)
            fill = TradeFillContract(
                root_contract_id=decision.root_contract_id,
                correlation_id=decision.correlation_id,
                parent_contract_id=decision.immutable_id,
                symbol=decision.symbol,
                side=decision.side,
                quantity=decision.quantity,
                fill_price=fill_price,
                fees=decision.expected_spread_cost
            )
            
            # Apply fill and spawn immutable successor snapshot
            next_snapshot, new_ledger_entries = self.accounting_engine.apply_fill(self.current_snapshot, fill)
            self.current_snapshot = next_snapshot
            self.ledger_history.extend(new_ledger_entries)

        self.snapshot_history.append(self.current_snapshot)
        return True
