import numpy as np
import pandas as pd
from typing import Dict, List, Any

class PerformanceStatistics:
    """
    Institutional analytics engine with automated frequency detection,
    calendar-day geometric CAGR, Sortino deviation, and recovery tracking.
    """
    
    def __init__(self, equity_curve: pd.Series, trades: List[Dict[str, Any]] = None, risk_free_rate: float = 0.06):
        self.equity_curve = equity_curve.sort_index()
        self.trades = trades or []
        self.rf = risk_free_rate
        self.daily_returns = self.equity_curve.pct_change().dropna()
        self.freq_info = self._detect_frequency()

    def _detect_frequency(self) -> Dict[str, Any]:
        if len(self.equity_curve) < 3:
            return {"frequency": "DAILY", "annualization_factor": 252}
            
        median_delta = pd.Series(self.equity_curve.index).diff().median().days
        if median_delta > 5:
            return {"frequency": "MONTHLY", "annualization_factor": 12}
        elif median_delta > 2:
            return {"frequency": "WEEKLY", "annualization_factor": 52}
        else:
            return {"frequency": "DAILY", "annualization_factor": 252}

    def compute_all(self) -> Dict[str, Dict[str, Any]]:
        return {
            "frequency_detection": self.freq_info,
            "return_metrics": self.return_metrics(),
            "risk_metrics": self.risk_metrics(),
            "trading_metrics": self.trading_metrics()
        }

    def return_metrics(self) -> Dict[str, float]:
        if len(self.equity_curve) < 2:
            return {"cagr": 0.0, "annualized_return": 0.0, "volatility": 0.0}
            
        calendar_days = (self.equity_curve.index[-1] - self.equity_curve.index[0]).days
        years = calendar_days / 365.25 if calendar_days > 0 else 1.0

        start_val = self.equity_curve.iloc[0]
        end_val = self.equity_curve.iloc[-1]
        
        cagr = (end_val / start_val) ** (1 / years) - 1.0 if start_val > 0 and years > 0 else 0.0
        ann_factor = self.freq_info["annualization_factor"]
        volatility = self.daily_returns.std() * np.sqrt(ann_factor)
        
        return {
            "cagr": round(cagr * 100, 2),
            "annualized_return": round(cagr * 100, 2),
            "volatility": round(volatility * 100, 2)
        }

    def risk_metrics(self) -> Dict[str, Any]:
        if len(self.daily_returns) == 0:
            return {
                "sharpe": 0.0, "sortino": 0.0, "calmar": 0.0, 
                "max_drawdown": 0.0, "drawdown_duration": 0, "recovery_duration": 0
            }
            
        ann_factor = self.freq_info["annualization_factor"]
        daily_rf = (1 + self.rf) ** (1 / ann_factor) - 1
        excess = self.daily_returns - daily_rf
        
        vol = self.daily_returns.std() * np.sqrt(ann_factor)
        sharpe = (excess.mean() / self.daily_returns.std()) * np.sqrt(ann_factor) if self.daily_returns.std() > 0 else 0.0
        
        downside = np.minimum(self.daily_returns - 0.0, 0)
        downside_dev = np.sqrt(np.mean(downside ** 2)) * np.sqrt(ann_factor)
        sortino = (excess.mean() * ann_factor) / downside_dev if downside_dev > 0 else 0.0
        
        rolling_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve - rolling_max) / rolling_max
        max_dd = drawdown.min()
        
        dd_duration = 0
        recovery_duration = 0
        if max_dd < 0:
            trough_idx = drawdown.idxmin()
            peak_idx = self.equity_curve.loc[:trough_idx].idxmax()
            peak_val = self.equity_curve.loc[peak_idx]
            
            dd_duration = (trough_idx - peak_idx).days
            post_trough = self.equity_curve.loc[trough_idx:]
            recovered = post_trough[post_trough >= peak_val]
            if not recovered.empty:
                recovery_duration = (recovered.index[0] - peak_idx).days
            else:
                recovery_duration = (self.equity_curve.index[-1] - peak_idx).days

        cagr = self.return_metrics()["cagr"] / 100.0
        calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0
        
        return {
            "sharpe": round(sharpe, 2),
            "sortino": round(sortino, 2),
            "calmar": round(calmar, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "drawdown_duration": int(dd_duration),
            "recovery_duration": int(recovery_duration)
        }

    def trading_metrics(self) -> Dict[str, float]:
        if not self.trades:
            return {"win_rate": 0.0, "profit_factor": 0.0, "expectancy": 0.0, "total_trades": 0}
            
        pnls = [t.get("pnl", 0.0) for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        win_rate = len(wins) / len(pnls) if len(pnls) > 0 else 0.0
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 1e-6
        profit_factor = gross_profit / gross_loss
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 0.0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
        return {
            "win_rate": round(win_rate * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy": round(expectancy, 2),
            "total_trades": len(pnls)
        }
