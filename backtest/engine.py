import numpy as np
from simulation.simulator import ClosedLoopSimulator
from attribution.engine import PerformanceAttributionEngine

class HistoricalBacktestEngine:
    """Drives the VSC closed-loop simulator across a historical multi-period time series."""

    def __init__(self, initial_capital: float = 1000000.0):
        self.simulator = ClosedLoopSimulator(initial_capital=initial_capital)
        self.attribution_engine = PerformanceAttributionEngine()

    def run_backtest(self, historical_market_series: list) -> dict:
        equity_curve = [self.simulator.current_snapshot.capital_base]
        
        for tick_data in historical_market_series:
            prices = tick_data.get("prices", {})
            orders = tick_data.get("orders", {})
            returns = tick_data.get("returns", np.random.normal(0.0005, 0.015, 252))

            market_payload = {
                "prices": prices,
                "returns": returns
            }

            # Execute simulation tick through the full architecture
            self.simulator.step(orders, market_payload)
            
            # Record total portfolio equity (Cash + Mark-to-Market Holdings)
            holdings_val = sum(pos.shares * prices.get(sym, pos.last_price) for sym, pos in self.simulator.current_snapshot.holdings.items())
            total_equity = self.simulator.current_snapshot.cash_balance + holdings_val
            equity_curve.append(total_equity)

        # Final attribution report over historical trajectory
        attribution = self.attribution_engine.evaluate(
            self.simulator.snapshot_history, 
            self.simulator.ledger_history
        )

        # Calculate max drawdown across equity curve
        eq_array = np.array(equity_curve)
        peak = np.maximum.accumulate(eq_array)
        drawdown = (eq_array - peak) / peak
        max_drawdown = float(np.min(drawdown))

        return {
            "equity_curve": equity_curve,
            "max_drawdown_pct": round(max_drawdown * 100, 2),
            "total_trades": len(self.simulator.ledger_history),
            "attribution": attribution
        }
