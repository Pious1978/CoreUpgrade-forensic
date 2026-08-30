import yfinance as yf
import pandas as pd

def analyze_trend(ticker_symbol):
    if not ticker_symbol.endswith((".NS", ".BO")):
        ticker_symbol += ".NS"
    
    df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        print(f"❌ Error: No data found for {ticker_symbol}.")
        return

    # Calculations
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['Vol_Avg'] = df['Volume'].rolling(window=20).mean()
    
    max_p = float(df['High'].max())
    min_p = float(df['Low'].min())
    diff = max_p - min_p
    fib_61 = max_p - (0.618 * diff)
    
    curr_p = float(df['Close'].iloc[-1])
    curr_v = float(df['Volume'].iloc[-1])
    ema20 = float(df['EMA20'].iloc[-1])
    ema50 = float(df['EMA50'].iloc[-1])
    vol_avg = float(df['Vol_Avg'].iloc[-1])

    # Logic for Dashboard
    is_above_ema20 = curr_p > ema20
    is_above_ema50 = curr_p > ema50
    holds_fib = curr_p >= fib_61
    vol_dryup = curr_v < vol_avg

    # Confidence Score Logic (Out of 10)
    score = 0
    if is_above_ema20: score += 3
    if is_above_ema50: score += 2
    if holds_fib: score += 3
    if vol_dryup: score += 2

    print(f"\n{'='*55}")
    print(f"🚀 {ticker_symbol} Trend Analysis — Decision Dashboard")
    print(f"{'='*55}")
    
    # 🎯 Verdict
    verdict_text = "🟢 BULLISH PULLBACK" if score >= 7 else "🟡 HIGH-CONFLICT ZONE" if score >= 5 else "🔴 BEARISH REVERSAL"
    print(f"🎯 Verdict\n{verdict_text}\n{'Bias remains positive' if score >=5 else 'Structure is weakening'} | Confidence: {score}/10")
    
    # 💹 Price Structure
    print(f"\n💹 Price Structure")
    print(f"CMP: ₹{curr_p:.2f}")
    print(f"EMA20: ₹{ema20:.2f} → {'Price above short-term trend' if is_above_ema20 else 'Price below short-term trend'}")
    print(f"EMA50: {'Holding' if is_above_ema50 else 'Breached'}")
    print(f"61.8% Fib: ₹{fib_61:.2f} → {'Currently being tested/holding' if holds_fib else 'Failed support'}")
    print(f"Previous Peak: ₹{max_p:.2f} → Not yet reclaimed")
    
    print(f"\nStructure Read:")
    print(f"Long-term: {'Uptrend intact' if is_above_ema50 else 'Threatened'}")
    print(f"Short-term: {'Consolidation' if holds_fib else 'Correction'}")
    print(f"Immediate: DECISION ZONE")

    # 📉 Volume Read
    print(f"\n📉 Volume Read")
    vol_emoji = "🟢" if vol_dryup else "🔴"
    print(f"{vol_emoji} {'Low-volume pullback (healthy dry-up)' if vol_dryup else 'High-volume selling (panic)'}")
    print(f"Interpretation: {'Selling pressure exhausted' if vol_dryup else 'Aggressive exit observed'}")

    # 📋 Actionable Trade Plan
    print(f"\n📋 Actionable Trade Plan")
    print(f"For Swing Buy:")
    print(f"  - Entry: Above ₹{curr_p * 1.03:.2f} on volume confirmation")
    print(f"  - Stop-loss: ₹{fib_61 * 0.98:.2f} (Close basis)")
    print(f"  - Targets: ₹{max_p:.2f} / ₹{max_p * 1.1:.2f}")
    
    print(f"For Existing Holders:")
    print(f"  - Hold only while above ₹{fib_61:.2f}")
    print(f"  - Reduce exposure below ₹{fib_61 * 0.98:.2f}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    user_ticker = input("Enter Ticker Name: ").strip().upper()
    if user_ticker:
        analyze_trend(user_ticker)