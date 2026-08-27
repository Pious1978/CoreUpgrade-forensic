import numpy as np
import pandas as pd
from typing import Dict, Any

class StressTestingEngine:
    """
    Evaluates portfolio resilience against historical market crash scenarios.
    """
    
    def __init__(self, portfolio_capital: float):
        self.capital = portfolio_capital
        
        # Standardized historical crisis shock vectors (Asset return percentages during shocks)
        self.historical_scenarios = {
            "COVID_19_CRASH_2020": {
                "description": "March 2020 global liquidity panic (-30% broad equity shock)",
                "market_shock": -0.30,
                "sector_shocks": {"FINANCIALS": -0.38, "IT": -0.22, "ENERGY": -0.45, "PHARMA": -0.12}
            },
            "GFC_2008_CRISIS": {
                "description": "October 2008 Lehman collapse (-50% systemic shock)",
                "market_shock": -0.50,
                "sector_shocks": {"FINANCIALS": -0.65, "IT": -0.42, "ENERGY": -0.48, "PHARMA": -0.30}
            },
            "FLASH_CRASH_2010": {
                "description": "Intraday liquidity vacuum shock (-9% flash drop)",
                "market_shock": -0.09,
                "sector_shocks": {"FINANCIALS": -0.12, "IT": -0.08, "ENERGY": -0.09, "PHARMA": -0.05}
            }
        }

    def run_stress_test(self, portfolio_weights: Dict[str, float], asset_betas: Dict[str, float]) -> Dict[str, Any]:
        """
        Calculates expected portfolio loss under each historical stress scenario.
        """
        results = {}
        
        for scenario_name, scenario in self.historical_scenarios.items():
            market_shock = scenario["market_shock"]
            total_loss_amount = 0.0
            
            for symbol, weight in portfolio_weights.items():
                beta = asset_betas.get(symbol, 1.0)
                asset_shock = market_shock * beta
                dollar_loss = self.capital * weight * asset_shock
                total_loss_amount += dollar_loss

            loss_pct = (total_loss_amount / self.capital) * 100
            
            results[scenario_name] = {
                "description": scenario["description"],
                "expected_portfolio_loss_pct": round(loss_pct, 2),
                "expected_dollar_loss": round(total_loss_amount, 2)
            }

        return {
            "portfolio_capital": self.capital,
            "scenarios_evaluated": results
        }
