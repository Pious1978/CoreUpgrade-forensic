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
    """Fetches the full master list from NSE using browser-like headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        print("📥 Downloading NSE Master List...")
        response = requests.get(NSE_MASTER_URL, headers=headers, timeout=15)
        response.raise_for_status() # Check if download was successful
        
        df = pd.read_csv(io.StringIO(response.text))
        # Remove any leading/trailing spaces in column names
        df.columns = df.columns.str.strip()
        # Only keep 'EQ' (Equity) series to avoid debt/gold bonds
        df = df[df['SERIES'] == 'EQ']
        return df['SYMBOL'].tolist()
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        # Manual fallback for your key stocks if NSE is blocking us
        return ["AWHCL", "ECORECO", "GRAVITA", "JSWINFRA", "AWL", "KPIT"]

def scan_vcp(symbol):
    """Full VCP Logic + Liquidity Filter."""
    try:
        session = Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0'})
        ticker = yf.Ticker(f"{symbol}.NS", session=session)
        
        # Download 1 year of data for EMA and 52-week High
        df = ticker.history(period="260d")
        
        # 1. LIQUIDITY FILTER (Crucial for full market scans)
        # Ignores stocks with average daily turnover < 25 Lakhs approx
        if df.empty or len(df) < 200: return False
        avg_volume = df['Volume'].tail(20).mean()
        if avg_volume < 50000: return False 

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

if __name__ == "__main__":
    symbols = get_nse_master_list()
    total = len(symbols)
    
    print(f"🔍 TOTAL STOCKS TO ANALYZE: {total}")
    print(f"🚀 STARTING DEEP MARKET SCAN... (Est: 20-30 mins)")
    
    alerts = []
    for i, sym in enumerate(symbols):
        if i % 50 == 0 and i > 0:
            print(f"Progress: {i}/{total} analyzed...")
            
        if scan_vcp(sym):
            print(f"🔥 VCP DETECTED: {sym}")
            alerts.append(sym)
        
        # Prevent Yahoo Finance from throttling your IP
        time.sleep(0.15) 

    print("\n" + "="*45)
    print(f"🎯 SCAN COMPLETE: {len(alerts)} ALERTS FOUND")
    print("="*45)
    for a in alerts:
        print(f"👉 {a}.NS")
    print("="*45)