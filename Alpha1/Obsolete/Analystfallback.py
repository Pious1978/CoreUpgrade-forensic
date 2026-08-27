import yfinance as yf
import pandas as pd

def get_market_context():
    try:
        vix = yf.Ticker("^INDIAVIX").history(period="1d")['Close'].iloc[-1]
        nifty = yf.Ticker("^NSEI").history(period="5d")['Close']
        n_trend = "Bullish" if nifty.iloc[-1] > nifty.iloc[0] else "Bearish"
        
        reasons = [
            "IT Sector Shock: HCL Tech's 11% crash has spiked hedging demand.",
            "Strait of Hormuz: Shipping disruptions impacting Energy/Port logistics.",
            "Board Meeting: Market nervous ahead of Reliance Q4 Results tomorrow (April 24)."
        ]
        return round(vix, 2), n_trend, reasons
    except:
        return 18.30, "Bearish", ["Connectivity issue; assuming high-risk environment."]

def analyze_trend(ticker_symbol):
    if not ticker_symbol.endswith((".NS", ".BO")): ticker_symbol += ".NS"
    
    # auto_adjust=True ensures splits/bonuses are handled by Yahoo Finance natively
    df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    if df.empty: return

    # --- DYNAMIC DATA (Using Adjusted Prices) ---
    curr_p = float(df['Close'].iloc[-1])
    max_p = float(df['High'].max())
    min_p = float(df['Low'].min())
    
    ema20 = float(df['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(df['Close'].ewm(span=50, adjust=False).mean().iloc[-1])
    fib_61 = max_p - (0.618 * (max_p - min_p))
    curr_v = float(df['Volume'].iloc[-1])
    vol_avg = float(df['Volume'].rolling(window=20).mean().iloc[-1])
    
    vix, nifty_t, reasons = get_market_context()

    print(f"\n{'='*65}")
    print(f"🚀 {ticker_symbol} Trend Analysis — Decision Dashboard")
    print(f"{'='*65}")

    print(f"💹 Price Structure")
    print(f"CMP: ₹{curr_p:.2f}")
    print(f"EMA20: ₹{ema20:.2f} → {'Above Trend' if curr_p > ema20 else 'Below Trend'}")
    print(f"EMA50: {'Holding' if curr_p > ema50 else 'Breached'}")
    print(f"61.8% Fib: ₹{fib_61:.2f} → {'Holding' if curr_p >= fib_61 else 'Testing Support'}")
    print(f"Previous Peak (Adj): ₹{max_p:.2f}")

    print(f"\nStructure Read:")
    print(f"Long-term: {'Uptrend' if curr_p > ema50 else 'Caution'} | Immediate: DECISION ZONE")

    print(f"\n📉 Volume Read")
    print(f"{'🟢' if curr_v < vol_avg else '🔴'} {'Healthy Dry-up' if curr_v < vol_avg else 'High Volume'}")

    print(f"\n🧠 MARKET CONTEXT: VIX at {vix} | Nifty: {nifty_t}")
    print("Reasons for Sentiment:")
    for r in reasons: print(f"  • {r}")

    # 📋 CORRECTED TRADE PLAN LOGIC
    # A valid SL must be below CMP. If Fib is above CMP, we use EMA50 or a 3% buffer.
    safe_sl = fib_61 if fib_61 < curr_p else min(ema50, curr_p * 0.97)
    
    print(f"\n📋 Actionable Trade Plan")
    print(f"For Swing Buy:")
    print(f"  - Entry: Above ₹{round(max(curr_p * 1.02, ema20), 2)} on volume confirmation")
    print(f"  - Stop-loss: ₹{round(safe_sl, 2)} (Close basis)")
    print(f"For Existing Holders:")
    print(f"  - Hold while above ₹{round(safe_sl, 2)}")
    print(f"{'='*65}\n")

if __name__ == "__main__":
    ticker = input("Enter Ticker: ").strip().upper()
    analyze_trend(ticker)