"""
validation/backtest_engine.py

Institutional-grade backtesting engine with look-ahead prevention (next-candle execution),
calendar-based CAGR, exposure metrics, and extended risk/expectancy analytics.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

class BacktestEngine:
    def __init__(
        self,
        df: pd.DataFrame,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        risk_free_rate: float = 0.06
    ):
        """
        df: DataFrame containing ['timestamp', 'open', 'high', 'low', 'close', 'signal']
        """
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.risk_free_rate = risk_free_rate
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: pd.DataFrame = pd.DataFrame()

    def run_backtest(self) -> Tuple[Dict[str, float], pd.DataFrame, List[Dict[str, Any]]]:
        if self.df.empty or 'signal' not in self.df.columns or 'close' not in self.df.columns:
            return self._empty_metrics(), pd.DataFrame(), []

        self._normalize_data()
        self._simulate_execution()
        metrics = self._calculate_performance_metrics()

        return metrics, self.equity_curve, self.trades

    def _normalize_data(self):
        if 'timestamp' in self.df.columns:
            self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
            self.df.sort_values('timestamp', inplace=True)
            self.df.reset_index(drop=True, inplace=True)
        
        # Enforce look-ahead prevention: Shift signal forward by 1 period 
        # so signals generated at close[t] execute at open[t+1]
        self.df['execution_signal'] = self.df['signal'].shift(1).fillna(0)

    def _simulate_execution(self):
        capital = self.initial_capital
        position = 0  # 0: Flat, 1: Long
        entry_price = 0.0
        entry_timestamp = None
        
        equity_records = []
        trades = []

        for i in range(len(self.df)):
            row = self.df.iloc[i]
            open_price = row.get('open', row['close'])
            close_price = row['close']
            exec_signal = row['execution_signal']
            timestamp = row['timestamp'] if 'timestamp' in self.df.columns else i

            # Strategy Execution Logic on Open (next-candle execution)
            if position == 0 and exec_signal == 1:
                position = 1
                entry_price = open_price * (1 + self.slippage_rate)
                entry_timestamp = timestamp
                capital -= (capital * self.commission_rate)
            elif position == 1 and exec_signal <= 0:
                exit_price = open_price * (1 - self.slippage_rate)
                pnl_pct = (exit_price - entry_price) / entry_price
                trade_pnl_abs = capital * pnl_pct
                capital += trade_pnl_abs - (capital * self.commission_rate)
                
                trades.append({
                    "entry_timestamp": entry_timestamp,
                    "exit_timestamp": timestamp,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "return_pct": pnl_pct,
                    "pnl_abs": trade_pnl_abs
                })
                position = 0

            # Current portfolio equity tracking based on close price
            current_equity = capital
            if position == 1:
                unrealized_pnl = (close_price - entry_price) / entry_price
                current_equity = capital * (1 + unrealized_pnl)

            equity_records.append({
                "timestamp": timestamp,
                "equity": current_equity,
                "position": position
            })

        self.equity_curve = pd.DataFrame(equity_records)
        self.trades = trades

    def _calculate_performance_metrics(self) -> Dict[str, float]:
        if self.equity_curve.empty:
            return self._empty_metrics()

        eq = self.equity_curve['equity']
        total_return = (eq.iloc[-1] - self.initial_capital) / self.initial_capital
        
        # Calendar-based CAGR calculation
        if 'timestamp' in self.equity_curve.columns and len(self.equity_curve) > 1:
            start_date = pd.to_datetime(self.equity_curve['timestamp'].iloc[0])
            end_date = pd.to_datetime(self.equity_curve['timestamp'].iloc[-1])
            days_diff = (end_date - start_date).days
            years = max(days_diff / 365.25, 0.01)
        else:
            years = len(self.equity_curve) / 252.0

        cagr = (eq.iloc[-1] / self.initial_capital) ** (1 / years) - 1

        # Win Rate & Expectancy
        winning_trades = [t for t in self.trades if t['return_pct'] > 0]
        losing_trades = [t for t in self.trades if t['return_pct'] <= 0]
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0.0
        loss_rate = 1.0 - win_rate

        avg_win = np.mean([t['return_pct'] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = abs(np.mean([t['return_pct'] for t in losing_trades])) if losing_trades else 0.0
        expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        # Profit Factor
        gross_profits = sum([t['pnl_abs'] for t in self.trades if t['pnl_abs'] > 0])
        gross_losses = abs(sum([t['pnl_abs'] for t in self.trades if t['pnl_abs'] < 0]))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else float('inf')

        # Maximum Drawdown & Calmar
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max
        max_drawdown = abs(drawdown.min())
        calmar_ratio = cagr / max_drawdown if max_drawdown > 0 else 0.0

        # Recovery Factor
        net_profit = eq.iloc[-1] - self.initial_capital
        recovery_factor = net_profit / abs(eq.min() - self.initial_capital) if abs(eq.min() - self.initial_capital) > 0 else float('inf')

        # Exposure % (Time in market)
        exposure = (self.equity_curve['position'] == 1).mean() if not self.equity_curve.empty else 0.0

        # Sharpe & Sortino (Annualized based on step returns)
        returns = eq.pct_change().dropna()
        excess_returns = returns - (self.risk_free_rate / 252)
        sharpe_ratio = (excess_returns.mean() / excess_returns.std()) * np.sqrt(252) if excess_returns.std() > 0 else 0.0
        
        downside_returns = returns[returns < 0]
        sortino_ratio = (excess_returns.mean() / downside_returns.std()) * np.sqrt(252) if not downside_returns.empty and downside_returns.std() > 0 else 0.0

        return {
            "total_return": round(total_return, 4),
            "cagr": round(cagr, 4),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(max_drawdown, 4),
            "calmar_ratio": round(calmar_ratio, 2),
            "recovery_factor": round(recovery_factor, 2),
            "expectancy": round(expectancy, 4),
            "exposure_pct": round(exposure, 4),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "total_trades": len(self.trades)
        }

    def _empty_metrics(self) -> Dict[str, float]:
        return {
            "total_return": 0.0, "cagr": 0.0, "win_rate": 0.0, "profit_factor": 0.0,
            "max_drawdown": 0.0, "calmar_ratio": 0.0, "recovery_factor": 0.0,
            "expectancy": 0.0, "exposure_pct": 0.0, "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0, "total_trades": 0
        }
