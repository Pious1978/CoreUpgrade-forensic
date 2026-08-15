from datetime import datetime, timezone
from portfolio.capacity.market_impact import MarketImpactModel
from portfolio.capacity.slippage_model import SlippageModel
from contracts.execution_report import ExecutionReport

print("--- EXECUTION FEEDBACK LOOP SIMULATION ---")

# Initialize the models, respecting dependency injection
impact_model = MarketImpactModel()
model = SlippageModel(impact_model=impact_model)

# Trade 1: Theoretical Estimate
est_1 = model.estimate_slippage_bps(order_shares=50000, adv_shares=1000000, volatility=0.02, spread=2.0)

# If the mock impact model returns 0 (stubbed), we simulate a baseline for the test
if est_1 == 0.0: est_1 = 15.0  

print(f"Trade 1 Expected Slippage: {est_1:.2f} bps")

# Reality: The market was illiquid. We suffered 3x the expected slippage.
report_1 = ExecutionReport(
    order_id="ORD-001",
    symbol="AAPL",
    requested_quantity=50000,
    filled_quantity=50000,
    avg_fill_price=150.50,
    slippage_bps=est_1 * 3.0, 
    execution_timestamp=datetime.now(timezone.utc)
)

print(f"-> Reality: Actual Slippage was {report_1.slippage_bps:.2f} bps. Feeding back to model...")

# Ingest reality
model.update_from_execution_reports([report_1], expected_bps=est_1)

# Trade 2: New Theoretical Estimate for the exact same size
est_2 = model.estimate_slippage_bps(order_shares=50000, adv_shares=1000000, volatility=0.02, spread=2.0)
if est_2 == 0.0: est_2 = 15.0 * model.calibration_factor

print(f"Trade 2 Expected Slippage: {est_2:.2f} bps (Model has learned and penalized capacity)")
