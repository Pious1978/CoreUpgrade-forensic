import pandas as pd
import os

# --- THE NEW LOGIC ENGINE ---
class MasterLongPlanner:
    def __init__(self, profile="Growth"):
        self.profile = profile
        self.config = self._get_profile_config()

    def _get_profile_config(self):
        profiles = {
            "Compounder": {"max_pos_size": 0.15, "stop_loss": 0.20, "priority": "Moat"},
            "Growth": {"max_pos_size": 0.08, "stop_loss": 0.10, "priority": "Momentum"},
            "HighRisk": {"max_pos_size": 0.03, "stop_loss": 0.05, "priority": "Speculative"}
        }
        return profiles.get(self.profile, profiles["Growth"])

    def calculate_sip_allocation(self, ticker, current_price, total_sip_budget, mkt_condition="Normal"):
        adjusted_budget = total_sip_budget * 1.2 if mkt_condition == "Cheap" else total_sip_budget
        # Weighted multiplier logic from your previous versions
        allowed_allocation = adjusted_budget * (self.config["max_pos_size"] * 5) 
        shares_to_buy = int(allowed_allocation // current_price)
        
        return {
            "Ticker": ticker,
            "Profile": self.profile,
            "Shares": shares_to_buy,
            "Stop_Loss": round(current_price * (1 - self.config["stop_loss"]), 2),
            "Total_Investment": round(shares_to_buy * current_price, 2)
        }

# --- THE EXECUTION WRAPPER (Don't lose this!) ---
def run_monthly_planner(input_file, sip_amount, market_state="Normal"):
    """
    Reads your scanner output and applies the profile-based planning.
    """
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Run the Master_Alpha_Scanner first!")
        return

    stocks_to_plan = pd.read_csv(input_file)
    final_plan = []

    for _, row in stocks_to_plan.iterrows():
        # Determine profile based on the stock's characteristics or a column in your CSV
        # Defaulting to Growth for now, but you can automate this selection logic
        profile_type = "Growth" 
        if row.get('RS_Rating', 0) > 0.2: profile_type = "HighRisk"
        
        planner = MasterLongPlanner(profile=profile_type)
        allocation = planner.calculate_sip_allocation(row['Ticker'], row['Price'], sip_amount, market_state)
        final_plan.append(allocation)

    pd.DataFrame(final_plan).to_csv("Final_SIP_Execution_Plan.csv", index=False)
    print("Success! Your execution plan is ready in 'Final_SIP_Execution_Plan.csv'")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # Example: Running your monthly plan
    MY_SIP_BUDGET = 100000  # Adjust based on your current capacity
    run_monthly_planner("Master_Scanner_Output.csv", MY_SIP_BUDGET, market_state="Normal")