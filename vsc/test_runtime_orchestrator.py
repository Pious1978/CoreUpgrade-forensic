import unittest
from datetime import datetime, timezone, timedelta
from runtime.freshness import MarketDataFreshnessMonitor
from runtime.state_store import ProductionStateStore
from runtime.scheduler import ProductionScheduler
from runtime.monitor import OperationalHealthDashboard

class TestVSC6_0ProductionRuntime(unittest.TestCase):

    def test_production_runtime_orchestration(self):
        print("\n==================================================")
        print(" Starting VSC 6.0 Production Runtime Test")
        print("==================================================")

        # 1. Test Production Scheduler Stages
        stages = ProductionScheduler.get_daily_workflow_stages()
        print(f"Workflow Stages Scheduled : {len(stages)} phases")
        for s in stages[:3]:
            print(f"  [{s['time']}] {s['stage']} -> {s['action']}")

        # 2. Test Production State Store
        state_store = ProductionStateStore(cash=1000000.0)
        state_store.update_state(cash=852451.50, holdings={"NVDA": 50.0, "MSFT": 300.0})
        print(f"State Store Initialized   : Portfolio={state_store.portfolio_id}, Cash=₹{state_store.cash:,.2f}")

        # 3. Test Market Data Freshness Monitor
        now = datetime.now(timezone.utc)
        fresh_ts = now - timedelta(seconds=1.5)
        stale_ts = now - timedelta(seconds=25.0)

        fresh_check = MarketDataFreshnessMonitor.check_freshness(fresh_ts, now)
        stale_check = MarketDataFreshnessMonitor.check_freshness(stale_ts, now)

        print(f"Data Freshness (Valid)    : Status={fresh_check['status']} (Age: {fresh_check['age_seconds']}s)")
        print(f"Data Freshness (Stale)    : Status={stale_check['status']} (Action: {stale_check['action']})")

        # 4. Test Operational Health Dashboard
        dashboard = OperationalHealthDashboard()
        health = dashboard.get_pipeline_health(fresh_check['status'], "APPROVED")
        print(f"Operational Health Status : {health['overall_status']}")
        for domain, stat in health['stages'].items():
            print(f"  {domain:12s} : {stat}")

        print("-" * 52)
        print("==================================================")
        print(" 🎉 VSC 6.0 Production Runtime & Monitoring Verified!")
        print("==================================================")

        # Assertions
        self.assertEqual(fresh_check['status'], "FRESH")
        self.assertEqual(stale_check['action'], "BLOCK_EXECUTION")
        self.assertEqual(health['overall_status'], "HEALTHY")
        self.assertEqual(len(stages), 7)

if __name__ == "__main__":
    unittest.main()
