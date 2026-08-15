import unittest
import numpy as np
from backtest.engine import HistoricalBacktestEngine

class TestVSC4_95HistoricalBacktest(unittest.TestCase):

    def test_historical_backtest_engine(self):
        print("\n==================================================")
        print(" Starting VSC 4.95 Historical Backtesting Engine Test")
        print("==================================================")

        # Mock historical multi-period time series data (3 trading ticks)
        historical_series = [
            {
                "date": "2026-01-02",
                "prices": {"NVDA": 900.0, "MSFT": 350.0},
                "orders": {
                    "NVDA": {"side": "BUY", "quantity": 100.0, "price": 900.0},
                    "MSFT": {"side": "BUY", "quantity": 300.0, "price": 350.0}
                }
            },
            {
                "date": "2026-01-03",
                "prices": {"NVDA": 930.0, "MSFT": 355.0},
                "orders": {
                    "MSFT": {"side": "BUY", "quantity": 100.0, "price": 355.0}
                }
            },
            {
                "date": "2026-01-06",
                "prices": {"NVDA": 950.0, "MSFT": 360.0},
                "orders": {
                    "NVDA": {"side": "SELL", "quantity": 50.0, "price": 950.0}
                }
            }
        ]

        backtest_engine = HistoricalBacktestEngine(initial_capital=1000000.0)
        results = backtest_engine.run_backtest(historical_series)
        attr = results["attribution"]

        print("\n--- Historical Backtest Performance Scorecard ---")
        print(f"Initial Capital          : ₹{attr.initial_capital:,.2f}")
        print(f"Final Equity             : ₹{attr.final_portfolio_value:,.2f}")
        print(f"Cumulative Return        : {attr.cumulative_return_pct:.2f}%")
        print(f"Maximum Drawdown         : {results['max_drawdown_pct']}%")
        print(f"Sharpe Ratio             : {attr.sharpe_ratio:.2f}")
        print(f"Total Transactions       : {results['total_trades']}")
        print(f"Signal Feedback Status   : {attr.signal_learning_feedback['learning_status']}")
        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 4.95 Historical Backtesting Engine Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertGreater(attr.final_portfolio_value, attr.initial_capital)
        self.assertEqual(results['total_trades'], 4)
        self.assertEqual(attr.signal_learning_feedback['learning_status'], "ADAPTIVE_BOOST_APPLIED")

if __name__ == "__main__":
    unittest.main()
