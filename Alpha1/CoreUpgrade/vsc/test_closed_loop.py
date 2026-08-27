import unittest
import numpy as np
from simulation.simulator import ClosedLoopSimulator

class TestVSC4_8ClosedLoopSimulator(unittest.TestCase):

    def test_closed_loop_simulation(self):
        print("\n==================================================")
        print(" Starting VSC 4.8 Closed-Loop Paper Trading Simulation")
        print("==================================================")

        sim = ClosedLoopSimulator(initial_capital=1000000.0)

        # --------------------------------------------------
        # Tick 1: Initial Acquisition of NVDA & MSFT (2 orders)
        # --------------------------------------------------
        market_data_t1 = {
            "prices": {"NVDA": 900.0, "MSFT": 350.0},
            "returns": np.random.normal(0.0005, 0.015, 252)
        }
        orders_t1 = {
            "NVDA": {"side": "BUY", "quantity": 100.0, "price": 900.0},
            "MSFT": {"side": "BUY", "quantity": 300.0, "price": 350.0}
        }

        success_t1 = sim.step(orders_t1, market_data_t1)
        self.assertTrue(success_t1)

        # --------------------------------------------------
        # Tick 2: Partial Rebalancing (Sell 50 NVDA) (1 order)
        # --------------------------------------------------
        market_data_t2 = {
            "prices": {"NVDA": 950.0, "MSFT": 360.0},
            "returns": np.random.normal(0.0005, 0.015, 252)
        }
        orders_t2 = {
            "NVDA": {"side": "SELL", "quantity": 50.0, "price": 950.0}
        }

        success_t2 = sim.step(orders_t2, market_data_t2)
        self.assertTrue(success_t2)

        print(f"\n--- Closed-Loop Simulation Summary ---")
        print(f"Total Snapshots Recorded : {len(sim.snapshot_history)}")
        print(f"Total Ledger Entries     : {len(sim.ledger_history)}")
        print(f"Final Portfolio Cash     : ₹{sim.current_snapshot.cash_balance:,.2f}")
        print(f"Final Holdings State     : {dict(sim.current_snapshot.holdings)}")
        print(f"Snapshot Lineage Chain   : v1 ──► v3 ──► v{sim.current_snapshot.version}")
        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 4.8 Closed-Loop Paper Trading Simulator Verified!")
        print("==================================================")

        # Invariant Assertions
        self.assertEqual(sim.current_snapshot.version, 4, "Snapshot version tracking failed across simulation ticks!")
        self.assertEqual(len(sim.snapshot_history), 3)
        self.assertEqual(len(sim.ledger_history), 3)
        self.assertGreater(sim.current_snapshot.cash_balance, 0.0)

if __name__ == "__main__":
    unittest.main()
