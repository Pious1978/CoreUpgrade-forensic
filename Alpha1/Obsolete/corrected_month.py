import yfinance as yf
import pandas as pd
import warnings
import urllib.request
import io

# Suppress warnings
warnings.filterwarnings('ignore')

def get_market_tickers():
    print("📥 Attempting to fetch the master list of NSE symbols...")
    tickers = []
    
    try:
        # Method 1: Try using nselib for the full 2,200+ list
        from nselib import capital_market
        equities_df = capital_market.equity_list()
        equities_df.columns = equities_df.columns.str.strip().str.upper()
        
        if 'SERIES' in equities_df.columns:
            tickers = equities_df[equities_df['SERIES'] == 'EQ']['SYMBOL'].tolist()
        else:
            tickers = equities_df['SYMBOL'].tolist()
            
        tickers = [str(t).strip() for t in tickers if str(t).strip() != '']
        print(f"✅ Successfully found {len(tickers)} active NSE equities.")
        
    except Exception as e:
        print(f"⚠️ NSE Website blocked the request: {e}")
        print("🔄 Switching to Fallback: Fetching the Nifty 500 Index...")
        
        # Method 2: Bulletproof Fallback (Nifty 500 directly from NSE CSV)
        try:
            url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req)
            nifty500_df = pd.read_csv(io.BytesIO(response.read()))
            tickers = nifty500_df['Symbol'].tolist()
            print(f"✅ Successfully loaded {len(tickers)} Nifty 500 stocks.")
        except Exception as e2:
            print(f"❌ Fallback also failed. Check internet connection. {e2}")
            return []
            
    return tickers

def find_market_wide_crashes(start_date, drop_threshold=-12.0):
    all_symbols = get_market_tickers()
    
    if not all_symbols:
        print("❌ Cannot proceed without ticker symbols.")
        return

    # Add .NS suffix for Yahoo Finance
    yf_tickers = [f"{sym}.NS" for sym in all_symbols]
    
    print(f"\n🔍 Scanning {len(yf_tickers)} stocks for a drop of {abs(drop_threshold)}% or more since {start_date}...")
    print("⏳ Bulk downloading data. This may take 1-3 minutes. Please wait...")

    crashed_stocks = []

    try:
        # BULK DOWNLOAD
        data = yf.download(yf_tickers, start=start_date, progress=True, threads=True)['Close']
        if isinstance(data, pd.Series):
             data = data.to_frame()
    except Exception as e:
        print(f"❌ Bulk download failed: {e}")
        return

    print("\n🧮 Processing data and calculating drops...")

    # Process each column
    for column_ticker in data.columns:
        clean_name = str(column_ticker).replace('.NS', '')
        stock_data = data[column_ticker].dropna()
        
        if len(stock_data) < 2:
            continue
            
        try:
            start_price = float(stock_data.iloc[0])
            current_price = float(stock_data.iloc[-1])
            
            if start_price <= 0:
                 continue
                 
            pct_change = ((current_price - start_price) / start_price) * 100
            
            # The Filter - Now checks against -12.0
            if pct_change <= drop_threshold:
                crashed_stocks.append({
                    'Ticker': clean_name,
                    'Start Price': round(start_price, 2),
                    'Current Price': round(current_price, 2),
                    'Drop (%)': round(pct_change, 2)
                })
        except Exception:
            pass

    # FORMAT AND DISPLAY
    if crashed_stocks:
        results_df = pd.DataFrame(crashed_stocks)
        results_df = results_df.sort_values(by='Drop (%)')
        results_df = results_df.reset_index(drop=True)
        
        print("\n" + "=" * 60)
        print(f"🚨 FOUND {len(crashed_stocks)} STOCKS DOWN {abs(drop_threshold)}%+ 🚨")
        print("=" * 60)
        print(results_df.to_string())
        print("=" * 60)
        
        filename = f"market_crash_{start_date}_12pct.csv"
        results_df.to_csv(filename, index=False)
        print(f"\n💾 Results successfully saved to: {filename}")
        
    else:
        print(f"\n✅ No stocks found that dropped {abs(drop_threshold)}% or more in this period.")

# ==========================================
# --- EXECUTION ENGINE (DO NOT DELETE) ---
# ==========================================
if __name__ == "__main__":
    # The date you want to measure the drop from
    target_start_date = "2026-02-11"
    
    # Run the scan! (Set to -12.0 for a 12% crash)
    find_market_wide_crashes(target_start_date, drop_threshold=-12.0)