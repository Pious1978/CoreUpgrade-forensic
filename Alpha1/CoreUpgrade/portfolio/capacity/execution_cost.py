from typing import Dict, Any

class ExecutionCostEngine:
    """Aggregates brokerage, STT, exchange fees, spread, and market impact into total execution cost."""
    
    def compute_total_cost(self, trade_value: float, slippage_bps: float, brokerage_bps: float = 3.0, stt_bps: float = 10.0) -> Dict[str, Any]:
        brokerage_cost = trade_value * (brokerage_bps / 10000.0)
        stt_cost = trade_value * (stt_bps / 10000.0)
        slippage_cost = trade_value * (slippage_bps / 10000.0)
        
        total_cost = brokerage_cost + stt_cost + slippage_cost
        total_cost_bps = (total_cost / trade_value) * 10000.0 if trade_value > 0 else 0.0

        return {
            "trade_value": round(trade_value, 2),
            "brokerage": round(brokerage_cost, 2),
            "stt": round(stt_cost, 2),
            "slippage_and_impact": round(slippage_cost, 2),
            "total_execution_cost": round(total_cost, 2),
            "total_cost_bps": round(total_cost_bps, 2)
        }
