import yfinance as yf
import pandas as pd
import time
import warnings

warnings.filterwarnings('ignore')

# --- CONFIGURATION ---
# Add your Smallcap 250 or personal watchlist here
WATCHLIST = ["GEOJITFSL.NS", "BLUEDART.NS", "GMDC.NS", "HINDCOPPER.NS", "IRCON.NS", "JSWINFRA.NS"] 
MARKET_CAP_MAX = 7500  # Cr (Adjusted for 2026 Smallcap levels)
PROFIT_MULTIPLIER = 2.0 # Minimum 2x growth in 4-5 years
MAX_PRICE_GROWTH = 1.5  # Max 50% price appreciation in 5 years (The "Stagnation" Filter)

def scan_undervalued_gems(tickers):
    results = []
    print(f"\n{'='*95}")
    print(f"SMALL-CAP VALUE NEXUS | SEARCHING FOR EARNINGS-PRICE DIVERGENCE")
    print(f"{'='*95}")
    print(f"{'TICKER':<15} | {'MCAP(Cr)':<10} | {'PROFIT GRW':<12} | {'PRICE GRW':<10} | {'DEBT/EQ':<8} | {'GAP'}")
    print(f"{'-'*95}")

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            
            # 1. Market Cap Filter
            mcap = info.get('marketCap', 0) / 10_000_000 
            if mcap > MARKET_CAP_MAX or mcap == 0: continue

            # 2. Profit Analysis (TTM vs 4 Years Ago)
            fin = t.financials 
            if fin.empty or len(fin.columns) < 4: continue
            
            curr_profit = fin.iloc[:, 0].get('Net Income', 0)
            old_profit = fin.iloc[:, -1].get('Net Income', 1) # Base year (approx 4y ago)
            
            if old_profit <= 0: continue 
            profit_growth = curr_profit / old_profit

            # 3. Price Analysis (Current vs 5 Years ago)
            hist = t.history(period="5y")
            if len(hist) < 500: continue
            
            curr_p = hist['Close'].iloc[-1]
            old_p = hist['Close'].iloc[0] 
            price_growth = curr_p / old_p

            # 4. Fundamental Health Check (Debt)
            debt_to_eq = info.get('debtToEquity', 0) / 100 # yf returns 100 for 1.0

            # 5. EXECUTION LOGIC: The "Gap" Discovery
            # We want Profit Growth to be MUCH higher than Price Growth
            val_gap = profit_growth / price_growth

            if profit_growth >= PROFIT_MULTIPLIER and price_growth <= MAX_PRICE_GROWTH:
                status = f"{val_gap:.1f}x GAP 🔥"
                print(f"{ticker:<15} | {int(mcap):<10} | {profit_growth:>10.1f}x | {price_growth:>9.1f}x | {debt_to_eq:>7.2f} | {status}")
                
                results.append({
                    "Ticker": ticker,
                    "Market Cap": round(mcap, 2),
                    "Profit Growth": round(profit_growth, 2),
                    "Price Growth": round(price_growth, 2),
                    "Debt/Equity": round(debt_to_eq, 2),
                    "Valuation Gap": round(val_gap, 2)
                })
            
            time.sleep(0.4) # Ethical scraping delay
        except Exception:
            continue

    print(f"{'='*95}\n")
    return pd.DataFrame(results)

if __name__ == "__main__":
    df = scan_undervalued_gems(WATCHLIST)
    if not df.empty:
        # Sort by the highest Valuation Gap
        df = df.sort_values(by='Valuation Gap', ascending=False)
        # Optional: df.to_excel("Hidden_Gems.xlsx", index=False)