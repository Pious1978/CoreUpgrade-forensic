from typing import List, Dict, Any, Tuple
from datetime import datetime
from .contracts import TradeRecord

class ExposureEngine:
    """
    Computes time-weighted Area Under Curve (AUC) portfolio exposure metrics, 
    thermal heat profiles, position statistics, capital turnover, and risk quality ratings.
    """
    
    def __init__(self, max_heat_threshold: float = 0.06, allow_leverage: bool = False):
        self.max_heat_threshold = max_heat_threshold  # e.g., 6.0% maximum allowed portfolio heat
        self.allow_leverage = allow_leverage          # If False, caps gross exposure at 100% (1.0)

    def analyze(self, trades: List[TradeRecord]) -> Dict[str, Any]:
        if not trades:
            return {
                "portfolio_heat": {"max_pct": 0.0, "average_pct": 0.0, "breaches": 0},
                "capital_exposure": {"max_pct": 0.0, "average_pct": 0.0},
                "position_statistics": {"max_concurrent_positions": 0, "average_positions": 0.0},
                "time_metrics": {"average_holding_days": 0.0, "capital_turnover": 0.0},
                "risk_quality": {"heat_rating": "UNCONSTRAINED", "concentration_warning": False}
            }

        events: List[Tuple[datetime, str, float, float]] = []
        for t in trades:
            weighted_risk = t.risk_pct * t.capital_weight
            capital_exp = t.capital_weight
            events.append((t.entry_date, "ENTER", weighted_risk, capital_exp))
            events.append((t.exit_date, "EXIT", weighted_risk, capital_exp))

        # Chronological sort. Prioritize EXITS over ENTERS at identical timestamps.
        events.sort(key=lambda x: (x[0], 0 if x[1] == "EXIT" else 1))

        start_time = events[0][0]
        end_time = events[-1][0]
        total_simulation_days = max(1, (end_time - start_time).days)

        current_heat = 0.0
        current_exposure = 0.0
        current_positions = 0

        heat_integral = 0.0
        exposure_integral = 0.0
        position_integral = 0.0

        heat_breach_count = 0
        max_heat = 0.0
        max_exposure = 0.0
        max_concurrent = 0

        last_time = start_time

        for curr_time, event_type, risk_val, exp_val in events:
            delta_days = (curr_time - last_time).days
            if delta_days > 0:
                heat_integral += current_heat * delta_days
                exposure_integral += current_exposure * delta_days
                position_integral += current_positions * delta_days
                last_time = curr_time

            if event_type == "ENTER":
                current_heat += risk_val
                current_exposure += exp_val
                current_positions += 1
            else:
                current_heat = max(0.0, current_heat - risk_val)
                current_exposure = max(0.0, current_exposure - exp_val)
                current_positions = max(0, current_positions - 1)

            if not self.allow_leverage:
                current_exposure = min(current_exposure, 1.0)

            max_heat = max(max_heat, current_heat)
            max_exposure = max(max_exposure, current_exposure)
            max_concurrent = max(max_concurrent, current_positions)

            if current_heat > self.max_heat_threshold:
                heat_breach_count += 1

        # Time-weighted averages (AUC / total days)
        avg_heat = heat_integral / total_simulation_days
        avg_exposure = exposure_integral / total_simulation_days
        avg_positions = position_integral / total_simulation_days

        max_heat_pct = round(max_heat * 100, 4)
        max_exposure_pct = round(max_exposure * 100, 2)
        avg_heat_pct = round(avg_heat * 100, 4)
        avg_exposure_pct = round(avg_exposure * 100, 2)

        # Time metrics
        total_holding_days = sum(t.holding_days for t in trades)
        avg_holding_days = total_holding_days / len(trades) if trades else 0.0
        capital_turnover = round((365.0 / avg_holding_days) * (avg_exposure), 2) if avg_holding_days > 0 else 0.0

        # Risk Quality Assessment
        heat_rating = "CONTROLLED"
        if heat_breach_count > 0:
            heat_rating = "ELEVATED_RISK" if heat_breach_count < 5 else "CRITICAL_BREACH"

        concentration_warning = max_exposure_pct > 100.0 or max_heat_pct > (self.max_heat_threshold * 100 * 1.5)

        return {
            "portfolio_heat": {
                "max_pct": max_heat_pct,
                "average_pct": avg_heat_pct,
                "breaches": heat_breach_count
            },
            "capital_exposure": {
                "max_pct": max_exposure_pct,
                "average_pct": avg_exposure_pct
            },
            "position_statistics": {
                "max_concurrent_positions": max_concurrent,
                "average_positions": round(avg_positions, 2)
            },
            "time_metrics": {
                "average_holding_days": round(avg_holding_days, 1),
                "capital_turnover": capital_turnover
            },
            "risk_quality": {
                "heat_rating": heat_rating,
                "concentration_warning": concentration_warning
            }
        }
