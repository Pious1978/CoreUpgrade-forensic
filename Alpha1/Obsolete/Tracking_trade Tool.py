import yfinance as yf
import pandas as pd
import os
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
TRADE_FILE = 'Trade.xlsx'
TOTAL_CAPITAL = 1000000 
MAX_RISK_INR = 500      
RR_RATIO = 2.0  # Aiming for 2x the risk taken (Risk-Reward 1:2)

def run_execution_terminal():
    if not os.path.exists(TRADE_FILE):
        print(f"❌ Error: {TRADE_FILE} not found.")
        return

    # Load Excel
    try:
        df = pd.read_excel(TRADE_FILE)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.dropna(subset=['Share Name'])
    except Exception as e:
        print(f"❌ Excel Error: {e}")
        return

    # UPDATED HEADER: Added TARGET column
    print(f"\n{'='*125}")
    print(f"PIYOOSH'S CONSOLIDATED DAILY TERMINAL")
    print(f"{'='*125}")
    print(f"{'SYMBOL':<12} | {'SIGNAL':<12} | {'LIVE':<8} | {'QTY':<5} | {'INVEST':<9} | {'ZONE':<10} | {'TARGET':<10}")
    print(f"{'-'*125}")

    map_fix = {
        "RIL": "RELIANCE", 
        "HINDCOOPER": "HINDCOPPER", 
        "DECNGOLD": "DECCANCE", 
        "DECCANGOLD": "DECCANCE",
        "ECORECO": "ECORECO"
    }

    for _, row in df.iterrows():
        try:
            name = str(row['Share Name']).strip().upper()
            clean_name = map_fix.get(name, name)
            
            t = f"{clean_name}.BO" if clean_name in ["ECORECO", "DECCANCE"] else f"{clean_name}.NS"
            
            data = yf.download(t, period="5d", progress=False, auto_adjust=True)
            if data.empty:
                continue

            if isinstance(data.columns, pd.MultiIndex):
                curr_p = float(data['Close'][t].iloc[-1])
            else:
                curr_p = float(data['Close'].iloc[-1])
            
            entry = float(row['Entry Zone'])
            sl = float(row['Stop Loss Price'])
            
            # --- CALCULATION LOGIC ---
            # 1. Calculate Risk taken per share at the Entry Zone
            risk_amount = entry - sl 
            
            # 2. Calculate Target Price (Entry + (Risk * RR_RATIO))
            # This ensures your target is mathematically tied to your risk
            target_p = entry + (risk_amount * RR_RATIO)
            
            if curr_p <= (entry * 1.015):
                signal = "💎 VALUE BUY"
            else:
                signal = "⏳ WAITING"

            risk_per_share = curr_p - sl
            qty = int(MAX_RISK_INR / risk_per_share) if risk_per_share > 5 else 0
            
            # Updated Print Statement
            print(f"{clean_name:<12} | {signal:<12} | {curr_p:<8.2f} | {qty:<5} | ₹{qty*curr_p:<8.0f} | {entry:<10.2f} | ₹{target_p:<9.2f}")

        except Exception:
            continue

    print(f"{'='*125}")

if __name__ == "__main__":
    run_execution_terminal()