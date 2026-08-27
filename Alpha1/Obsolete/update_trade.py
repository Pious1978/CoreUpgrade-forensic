import yfinance as yf
import pandas as pd
import warnings
import urllib.request
import io
import os
from datetime import datetime

# --- SETTINGS ---
warnings.filterwarnings('ignore')
TRADE_FILE = 'Trade.xlsx'
TOTAL_CAPITAL = 1000000 
MAX_RISK_INR = 500      
RR_RATIO = 2.0
CRASH_THRESHOLD = -12.0 # Looking for 12% drops
TARGET_START_DATE = "2026-02-11" # Date to measure crash from

# --- UTILITIES ---
def get_market_tickers():
    """Fetches NSE symbols with bulletproof fallback."""
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        df = pd.read_csv(io.BytesIO(response.read()))
        return df['Symbol'].tolist()
    except Exception as e:
        print(f"⚠️ Falling back to manual list due to connection error: {e}")
        return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]

def save_to_trade_log(new_data):
    """Saves or updates the entry in your Master Trade Excel."""
    if not os.path.exists(TRADE_FILE):
        # Create file with headers if it doesn't exist
        pd.DataFrame(columns=['Sr No', 'Share Name', 'Entry Zone', 'Stop Loss Price', 'Quantity to Buy']).to_excel(TRADE_FILE, index=False)

    while True:
        try:
            df = pd.read_excel(TRADE_FILE)
            symbol = new_data['Share Name']
            
            # Update if exists, otherwise append
            mask = df['Share Name'].astype(str).str.upper() == str(symbol).upper()
            if mask.any():
                idx = df[mask].index[0]
                for col, val in new_data.items():
                    if col in df.columns: df.at[idx, col] = val
                print(f"🔄 Updated {symbol} in log.")
            else:
                next_sr = df['Sr No'].max() + 1 if not df.empty else 1
                new_data['Sr No'] = next_sr
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
                print(f"➕ Added {symbol} to log.")

            df.to_excel(TRADE_FILE, index=False)
            break
        except PermissionError:
            input(f"⚠️ {TRADE_FILE} is open! Please close it and press Enter...")

# --- CORE ENGINE ---
def run_crash_recovery_log():
    symbols = get_market_tickers()
    yf_tickers = [f"{s}.NS" for s in symbols]
    
    print(f"🔍 Scanning {len(yf_tickers)} stocks for >{abs(CRASH_THRESHOLD)}% drop since {TARGET_START_DATE}...")
    
    try:
        # Bulk Download for speed
        data = yf.download(yf_tickers, start=TARGET_START_DATE, progress=True, threads=True)['Close']
        if isinstance(data, pd.Series): data = data.to_frame()
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    crashed_candidates = []
    
    for ticker in data.columns:
        stock_series = data[ticker].dropna()
        if len(stock_series) < 2: continue
        
        start_p = float(stock_series.iloc[0])
        current_p = float(stock_series.iloc[-1])
        pct_change = ((current_p - start_p) / start_p) * 100
        
        if pct_change <= CRASH_THRESHOLD:
            # Calculate Risk-Based Quantity
            # Using 6-month low as a logical Stop Loss
            try:
                hist = yf.Ticker(ticker).history(period="6mo")
                low_6m = float(hist['Low'].min())
                risk_ps = round(current_p - low_6m, 2)
                
                # If risk is too small or negative, default to 5% SL
                if risk_ps <= 0: risk_ps = current_p * 0.05 
                
                qty = int(MAX_RISK_INR / risk_ps)
                
                crashed_candidates.append({
                    'Share Name': ticker.replace('.NS', ''),
                    'Entry Zone': round(current_p, 2),
                    'Drop (%)': round(pct_change, 2),
                    'Stop Loss Price': round(current_p - risk_ps, 2),
                    'Quantity to Buy': qty,
                    'Total Investment': round(qty * current_p, 2),
                    'Date_Flagged': datetime.now().strftime("%Y-%m-%d")
                })
            except: continue

    # Display and Save
    if crashed_candidates:
        results_df = pd.DataFrame(crashed_candidates).sort_values(by='Drop (%)')
        print("\n" + "!"*30)
        print(f"🚨 FOUND {len(results_df)} CRASHED OPPORTUNITIES 🚨")
        print(results_df[['Share Name', 'Drop (%)', 'Entry Zone', 'Quantity to Buy']].to_string())
        
        choice = input("\n👉 Do you want to log these into your Trade.xlsx? (y/n): ")
        if choice.lower() == 'y':
            for stock in crashed_candidates:
                save_to_trade_log(stock)
    else:
        print("✅ No major crashes found in the current selection.")

if __name__ == "__main__":
    run_crash_recovery_log()