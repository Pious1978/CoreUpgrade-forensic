import pandas as pd
import yfinance as yf
from datetime import datetime

# --- ORIGINAL CONFIGURATION ---
PORTFOLIO_FILE = "My_Holdings.xlsx"
TICKER_MAP = {
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "TITAN": "TITAN.NS",
    # Add your other manual mappings here
}

# Original Budget Allocation
BUDGETS = {
    "Compounder": 25000,
    "Growth": 15000,
    "HighRisk": 10000
}

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="1y")
        if df.empty: return None
        
        curr_price = df['Close'].iloc[-1]
        sma200 = df['Close'].rolling(window=200).mean().iloc[-1]
        mom_63 = ((df['Close'].iloc[-1] / df['Close'].iloc[-63]) - 1) * 100
        volatility = df['Close'].pct_change().std() * (252**0.5) # Annualized Vol
        
        return {
            "Price": curr_price,
            "SMA200": sma200,
            "Momentum_63": mom_63,
            "Volatility": volatility
        }
    except:
        return None

def run_original_planner():
    print(f"--- Starting Portfolio Analysis: {datetime.now().strftime('%Y-%m-%d')} ---")
    
    # Load your manual watchlist/holdings
    try:
        data = pd.read_excel(PORTFOLIO_FILE)
    except FileNotFoundError:
        print("Error: My_Holdings.xlsx not found.")
        return

    results = []

    for index, row in data.iterrows():
        stock_name = row['Stock']
        category = row['Category'] # Compounder, Growth, or HighRisk
        ticker = TICKER_MAP.get(stock_name, f"{stock_name}.NS")
        
        stats = get_stock_data(ticker)
        if stats:
            # Original Logic: Check if price is above 200 SMA
            trend = "BULLISH" if stats['Price'] > stats['SMA200'] else "BEARISH"
            
            # Original Allocation Math
            budget = BUDGETS.get(category, 10000)
            qty_to_buy = int(budget // stats['Price'])
            
            results.append({
                "Stock": stock_name,
                "Category": category,
                "Price": round(stats['Price'], 2),
                "Trend": trend,
                "Mom_63D": round(stats['Momentum_63'], 2),
                "Qty_to_Buy": qty_to_buy,
                "Total_Cost": round(qty_to_buy * stats['Price'], 2)
            })
            print(f"Processed: {stock_name}")

    # Export to Excel
    output_df = pd.DataFrame(results)
    output_name = f"SIP_Plan_{datetime.now().strftime('%b_%Y')}.xlsx"
    output_df.to_excel(output_name, index=False)
    print(f"\nSuccess! Plan saved to {output_name}")

if __name__ == "__main__":
    run_original_planner()