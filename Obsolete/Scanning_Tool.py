import yfinance as yf
import pandas as pd
import warnings
import os

warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
TOTAL_CAPITAL = 1000000 
MAX_RISK_INR = 500      
RR_RATIO = 2.0
TRADE_FILE = 'Trade.xlsx'

# ANSI Colors for Terminal Highlighting
BOLD = '\033[1m'
GREEN = '\033[92m'
CYAN = '\033[96m'
END = '\033[0m'

def get_nifty_500_tickers():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    try:
        df = pd.read_csv(url)
        return df[['Symbol', 'Series']]
    except:
        # Fallback list
        return pd.DataFrame({'Symbol': ['RELIANCE', 'HDFCBANK', 'HAL', 'JSWINFRA']})

def load_watchlist():
    """Load Trade.xlsx and return a set of symbols for O(1) lookup"""
    if not os.path.exists(TRADE_FILE):
        print(f"⚠️  Note: {TRADE_FILE} not found.")
        return set()
    
    try:
        # Handling potential formatting issues in Excel
        df = pd.read_excel(TRADE_FILE)
        df.columns = [str(c).strip() for c in df.columns]
        # Change 'Share Name' to whatever your column header is in Excel
        target_col = 'Share Name' if 'Share Name' in df.columns else df.columns[0]
        symbols = set(df[target_col].dropna().astype(str).str.upper().str.strip())
        return symbols
    except Exception as e:
        print(f"❌ Error loading watchlist: {e}")
        return set()

def run_market_scanner():
    n500 = get_nifty_500_tickers()
    watchlist = load_watchlist()
    results = []

    print(f"🚀 Starting Market Scan (Nifty 500) | Comparing with {len(watchlist)} items in Watchlist...")

    # For testing, you can use n500.head(20) to ensure it works quickly
    for _, row in n500.iterrows():
        symbol = row['Symbol']
        ticker = f"{symbol}.NS"
        
        try:
            # Price Data (6 months)
            data = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
            if data.empty: continue
            
            # Flatten columns if MultiIndex (common in latest yfinance)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            close_p = data['Close'].iloc[-1]
            high_6m = data['High'].max()
            low_6m = data['Low'].min()
            
            # Simple Market Cap Logic (Note: yf.info is slow, using 1mo avg volume * price as a proxy is faster, 
            # but for accuracy, we'll keep your category logic if you prefer it)
            # To speed up, we skip yf.Ticker(ticker).info and categorize by price/vol or skip
            category = "N/A"
            cat_rank = 0

            # Fibonacci Logic
            fib_value_zone = high_6m - (0.618 * (high_6m - low_6m))
            stop_loss = low_6m
            
            signal = "💎 VALUE BUY" if close_p <= (fib_value_zone * 1.05) else "⏳ WAITING"
            risk_amt = fib_value_zone - stop_loss
            target_p = fib_value_zone + (risk_amt * RR_RATIO)
            
            risk_ps = close_p - stop_loss
            qty = int(MAX_RISK_INR / risk_ps) if risk_ps > 5 else 0

            # --- WATCHLIST MATCH CHECK ---
            is_match = symbol.upper() in watchlist
            match_flag = "⭐" if is_match else ""

            results.append({
                'MATCH': match_flag,
                'SYMBOL': symbol,
                'SIGNAL': signal,
                'LIVE': round(float(close_p), 2),
                'QTY': qty,
                'INVEST': round(qty * close_p, 0),
                'ZONE': round(float(fib_value_zone), 2),
                'TARGET': round(float(target_p), 2),
                'MATCH_RANK': 0 if is_match else 1 # Matches come first
            })
            
        except Exception:
            continue

    if not results:
        print("No results found.")
        return

    # --- SORTING & DISPLAY ---
    master_df = pd.DataFrame(results)
    master_df['SIG_RANK'] = master_df['SIGNAL'].apply(lambda x: 0 if x == "💎 VALUE BUY" else 1)
    
    # Sort: First by Watchlist Match, then by Buy Signal
    sorted_df = master_df.sort_values(by=['MATCH_RANK', 'SIG_RANK'])

    print(f"\n{'='*120}")
    print(f"{'M':<2} | {'SYMBOL':<15} | {'SIGNAL':<12} | {'LIVE':<8} | {'QTY':<5} | {'INVEST':<10} | {'FIB ZONE':<10} | {'TARGET'}")
    print(f"{'-'*120}")

    for _, r in sorted_df.head(50).iterrows():
        # Add visual color to matches
        line = f"{r['MATCH']:<2} | {r['SYMBOL']:<15} | {r['SIGNAL']:<12} | {r['LIVE']:<8.2f} | {r['QTY']:<5} | ₹{r['INVEST']:<9.0f} | {r['ZONE']:<10.2f} | ₹{r['TARGET']:.2f}"
        
        if r['MATCH'] == "⭐":
            print(f"{BOLD}{CYAN}{line}{END}") # Highlight matching stocks
        else:
            print(line)

    print(f"{'='*120}")

if __name__ == "__main__":
    run_market_scanner()