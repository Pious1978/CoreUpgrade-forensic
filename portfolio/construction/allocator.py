from typing import List, Dict
from research.adapter import ResearchCandidate
from portfolio.snapshot import PortfolioSnapshot
from .constraints import PortfolioConstraintEngine

class RiskAwareAllocator:
    def __init__(self, constraint_engine: PortfolioConstraintEngine = None):
        self.constraint_engine = constraint_engine or PortfolioConstraintEngine()

    def allocate(
        self, 
        approved_candidates: List[ResearchCandidate], 
        snapshot: PortfolioSnapshot
    ) -> Dict[str, float]:
        if not approved_candidates:
            return {}

        total_value = snapshot.total_portfolio_value
        if total_value <= 0:
            total_value = snapshot.capital_base

        # Calculate existing portfolio weights from snapshot holdings
        existing_weights = {
            sym: pos.market_value / total_value 
            for sym, pos in snapshot.holdings.items()
        }

        # 1. Get risk-adjusted scores (volatility penalized)
        adjusted_scores = self.constraint_engine.apply_risk_adjustments(approved_candidates)
        total_score = sum(adjusted_scores.values())

        if total_score == 0:
            return {}

        # 2. Available capital for investment (accounting for mandatory cash reserve)
        investable_capital_ratio = 1.0 - self.constraint_engine.min_cash_reserve
        raw_target_weights = {
            symbol: (score / total_score) * investable_capital_ratio 
            for symbol, score in adjusted_scores.items()
        }

        # 3. State-aware rebalancing: check existing exposure against concentration caps
        final_weights = {}
        max_cap = self.constraint_engine.max_concentration

        for symbol, target_w in raw_target_weights.items():
            current_w = existing_weights.get(symbol, 0.0)
            
            # If current holding already exceeds or meets the max cap, do not allocate more
            if current_w >= max_cap:
                final_weights[symbol] = 0.0
            else:
                final_weights[symbol] = min(target_w, max_cap)

        # Normalize remaining active weights to sum up to the investable ratio
        allocated_sum = sum(final_weights.values())
        if allocated_sum > 0 and allocated_sum < investable_capital_ratio:
            scale = investable_capital_ratio / allocated_sum
            final_weights = {s: w * scale for s, w in final_weights.items()}

        total_allocated = sum(final_weights.values())
        cash_weight = 1.0 - total_allocated

        print(f"\n--- VSC 3.1 State-Aware Portfolio Rebalancing ---")
        print(f"Portfolio ID: {snapshot.portfolio_id} | Version: {snapshot.version} | Total Value: ₹{total_value:,.2f}")
        print(f"{'Symbol':<10} | {'Current Wt':<12} | {'Target Wt':<12} | {'Allocated Wt':<14} | {'Capital (₹)':<15}")
        print("-" * 72)
        
        for symbol, weight in final_weights.items():
            current_w = existing_weights.get(symbol, 0.0)
            target_w = raw_target_weights.get(symbol, 0.0)
            allocated_capital = weight * total_value
            print(f"{symbol:<10} | {current_w*100:>10.1f}% | {target_w*100:>10.1f}% | {weight*100:>12.1f}% | ₹{allocated_capital:>13,.2f}")
            
        print(f"{'CASH':<10} | {'N/A':<12} | {'N/A':<12} | {cash_weight*100:>12.1f}% | ₹{cash_weight*total_value:>13,.2f}")
        print("-" * 72)

        return final_weights
