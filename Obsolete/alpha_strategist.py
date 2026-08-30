import yfinance as yf
import pandas as pd
import warnings
import os
import config  # <--- Importing your central settings

warnings.filterwarnings('ignore')

# Colors for Terminal
BOLD = '\033[1m'
GREEN = '\033[92m'
CYAN = '\033[96m'
END = '\033[0m'

def save_to_excel(new_data):
    """Integrates the Auto-Updater logic to save/update the Excel sheet."""
    if not os.path.exists(config.TRADE_FILE):
        print(f"❌ Error: {config.TRADE_FILE} not found!")
        return

    while True:
        try:
            df = pd.read_excel(config.TRADE_FILE)
            df.columns = [str(c).strip() for c in df.columns]

            symbol = new_data['Share Name']
            mask = df['Share Name'].astype(str).str.upper().str.strip() == symbol
            
            if mask.any():
                print(f"🔄 Updating existing research for {symbol}...")
                idx = df[mask].index[0]
                for col, val in new_data.items():
                    if col in df.columns:
                        df.at[idx, col] = val
            else:
                print(f"➕ Adding new research entry for {symbol}...")
                next_sr = df['Sr No'].max() + 1 if 'Sr No' in df.columns and not df.empty else 1
                new_data['Sr No'] = next_sr
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)

            df.to_excel(config.TRADE_FILE, index=False)
            print(f"✅ Successfully updated {config.TRADE_FILE}!")
            break
        except PermissionError:
            input(f"⚠️ {config.TRADE_FILE} is OPEN. Please close it and press Enter...")
        except Exception as e:
            print(f"❌ Error saving: {e}")
            break

def run_unified_scanner():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        n500 = pd.read_csv(url)
    except:
        print("❌ Could not fetch Nifty 500 list. Check internet connection.")
        return

    print(f"🚀 Scanning Nifty 500 | Capital: ₹{config.TOTAL_CAPITAL} | Risk: ₹{config.MAX_RISK_INR}")

    # Process first 50 for testing; remove .head(50) for full scan
    for _, row in n500.head(50).iterrows(): 
        symbol = row['Symbol']
        ticker = f"{symbol}.NS"
        
        try:
            data = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
            if data.empty: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)

            close_p = float(data['Close'].iloc[-1])
            high_6m = float(data['High'].max())
            low_6m = float(data['Low'].min())
            
            # 61.8% Fibonacci Retracement Calculation
            fib_zone = high_6m - (0.618 * (high_6m - low_6m))
            
            # Entry trigger: Price is within 5% of the 61.8% Retracement Zone
            if close_p <= (fib_zone * 1.05):
                risk_ps = round(close_p - low_6m, 2)
                
                # Position Sizing based on config.MAX_RISK_INR
                qty = int(config.MAX_RISK_INR / risk_ps) if risk_ps > 1.0 else 0
                
                trade_info = {
                    'Share Name': symbol,
                    'Portfolio Capital (₹)': config.TOTAL_CAPITAL,
                    'Entry Zone': round(close_p, 2),
                    'Value Zone (Nifty 24k)': round(fib_zone, 2),
                    'Stop Loss Price': round(low_6m, 2),
                    'Exit Levels': round(fib_zone + ((fib_zone - low_6m) * config.RR_RATIO), 2),
                    'Risk per Share': risk_ps,
                    'Quantity to Buy': qty,
                    'Total Investment': round(qty * close_p, 2)
                }
                
                print(f"\n{GREEN}🎯 SIGNAL FOUND: {symbol}{END}")
                print(f"Live: {close_p} | 61.8% Zone: {round(fib_zone, 2)} | Qty: {qty}")
                
                choice = input(f"👉 Add {symbol} to Trade Sheet? (y/n): ").lower()
                if choice == 'y':
                    save_to_excel(trade_info)

        except Exception:
            continue

if __name__ == "__main__":
    run_unified_scanner()