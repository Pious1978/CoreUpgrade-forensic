import yfinance as yf
import pandas as pd
import requests
import io
import time
from requests import Session

# --- CONFIGURATION ---
# The master list of all listed companies on NSE
NSE_MASTER_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

def get_nse_master_list():
    """Fetches the full master list from NSE using proper browser headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/csv'
    }
    try:
        print("📥 Downloading NSE Master List (Full Market)...")
        response = requests.get(NSE_MASTER_URL, headers=headers, timeout=15)
        response.raise_for_status() 
        
        df = pd.read_csv(io.StringIO(response.text))
        # Clean column names (NSE often has leading spaces like ' SYMBOL')
        df.columns = df.columns.str.strip()
        # Series 'EQ' ensures we scan regular stocks, not debt/gold bonds
        df = df[df['SERIES'] == 'EQ']
        return df['SYMBOL'].tolist()
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        # Manual fallback to your core watchlist if the server is down
        return ["AWHCL", "ECORECO", "GRAVITA", "JSWINFRA", "KPITTECH", "MAZDOCK"]

def scan_vcp(symbol):
    """Full VCP Logic + Liquidity Guard."""
    try:
        session = Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        ticker = yf.Ticker(f"{symbol}.NS", session=session)
        
        # Download 250 days for EMA and 52-week High analysis
        df = ticker.history(period="250d")
        
        if df.empty or len(df) < 200: return False

        # 1. LIQUIDITY FILTER (The 'Dead Stock' Guard)
        # Average Daily Turnover Check: Average Volume * Average Price
        # We ignore stocks trading less than ~25-50 Lakhs daily on average
        avg_volume_20d = df['Volume'].tail(20).mean()
        avg_price = df['Close'].tail(20).mean()
        daily_turnover = avg_volume_20d * avg_price
        
        if daily_turnover < 2500000: # 25 Lakhs threshold
            return False

        # 2. TREND FILTER (Stage 2 Momentum)
        ema_200 = df['Close'].ewm(span=200).mean().iloc[-1]
        ema_50 = df['Close'].ewm(span=50).mean().iloc[-1]
        cmp = df['Close'].iloc[-1]
        if not (cmp > ema_50 > ema_200): return False

        # 3. VCP TIGHTNESS (ATR Reduction)
        df['ATR_Pct'] = ((df['High'] - df['Low']) / df['Close']) * 100
        recent_vol = df['ATR_Pct'].tail(10).mean()   
        historic_vol = df['ATR_Pct'].tail(60).mean() 
        is_tight = recent_vol < (historic_vol * 0.55)

        # 4. PIVOT CHECK (Within 8% of 52-Week High)
        high_52 = df['High'].max()
        is_at_pivot = cmp >= (high_52 * 0.92)

        return is_tight and is_at_pivot
    except:
        return False

# --- EXECUTION ---
if __name__ == "__main__":
    symbols = get_nse_master_list()
    total = len(symbols)
    
    print(f"🔍 TOTAL LISTED STOCKS DETECTED: {total}")
    print(f"🚀 STARTING FULL MARKET SCAN (This may take 20-30 mins)...")
    
    alerts = []
    for i, sym in enumerate(symbols):
        # Progress Tracking
        if i % 50 == 0 and i > 0:
            print(f"Progress: {i}/{total} analyzed...")
            
        if scan_vcp(sym):
            print(f"🔥 VCP ALERT: {sym}.NS matches criteria!")
            alerts.append(sym)
        
        # Throttling to prevent Yahoo Finance from blocking your IP
        time.sleep(0.15) 

    print("\n" + "="*45)
    print(f"🎯 SCAN COMPLETE: {len(alerts)} ALERTS FOUND")
    print("="*45)
    if alerts:
        for a in alerts:
            print(f"👉 {a}.NS")
    else:
        print("No active VCP setups found in the current market.")
    print("="*45)