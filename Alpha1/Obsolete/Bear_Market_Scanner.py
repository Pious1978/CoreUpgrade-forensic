import yfinance as yf
import pandas as pd
from datetime import datetime

# =========================
# YOUR STOCK UNIVERSE
# =========================
CORE_STOCKS = [
    "DIXON","KAYNES","AMBER","LT","CONCOR","ADANIPORTS","HAL","BEL",
    "TATAPOWER","NTPC","BSE","HDFCAMC","INFY","SIEMENS","ABB",
    "HCLTECH","360ONE","RELIANCE","TCS","TITAN","M&M","SRF",
    "AARTIIND","NAM-INDIA","CAMS","FLUOROCHEM","PIIND",
    "DEEPAKNTR","NAVINFLUOR"
]

GROWTH_STOCKS = [
    "CYIENTDLM","KIRLOSENG","GPPL","THERMAX","MAZDOCK",
    "DATAPATTNS","BDL","ADANIGREEN","ANGELONE","KPITTECH",
    "MARUTI","TATAELXSI","PERSISTENT","CYIENT","JSWENERGY",
    "COFORGE","TRENT","EICHERMOT","NEOGEN","AMIORG"
]

SCAN_UNIVERSE = CORE_STOCKS + GROWTH_STOCKS


# =========================
# FETCH FUNCTION (NSE + BSE)
# =========================
def fetch_stock_data(symbol):
    possible = [symbol + ".NS", symbol + ".BO", symbol]

    for sym in possible:
        try:
            df = yf.download(sym, period="1y", interval="1d", progress=False)
            if not df.empty and len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df, sym
        except:
            continue

    return None, None


# =========================
# ANALYSIS ENGINE
# =========================
def analyze_stock(symbol):
    df, used_symbol = fetch_stock_data(symbol)

    if df is None:
        return None

    # Indicators
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()
    df['Vol_Avg'] = df['Volume'].rolling(20).mean()

    curr = df['Close'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    vol = df['Volume'].iloc[-1]
    vol_avg = df['Vol_Avg'].iloc[-1]

    # Trend
    trend_strong = ema20 > ema50 and curr > ema20

    # Recent structure (better than full-year fib)
    recent_high = df['High'].tail(60).max()
    recent_low = df['Low'].tail(60).min()

    fib_61 = recent_high - (0.618 * (recent_high - recent_low))

    # Pullback logic
    pullback = curr > fib_61 and curr > ema50

    # Volume dry-up
    vol_dry = vol < vol_avg

    # Scoring
    score = 0
    if trend_strong: score += 1
    if curr > ema50: score += 1
    if curr > fib_61: score += 1
    if vol_dry: score += 1

    if score < 3:
        return None  # Filter weak setups

    # Trade Plan
    entry = round(curr, 2)
    stop = round(ema50, 2)
    target = round(recent_high, 2)
    rr = round((target - entry) / (entry - stop), 2) if (entry - stop) > 0 else 0

    return {
        "Stock": used_symbol,
        "Price": entry,
        "Score": score,
        "Trend": "Strong" if trend_strong else "Weak",
        "Volume": "Dry" if vol_dry else "High",
        "Entry": entry,
        "Stop Loss": stop,
        "Target": target,
        "R:R": rr
    }


# =========================
# MAIN SCANNER
# =========================
def run_scanner():
    print("\n🔍 Running Bear Market Scanner...\n")

    results = []

    for stock in SCAN_UNIVERSE:
        res = analyze_stock(stock)
        if res:
            results.append(res)

    if not results:
        print("❌ No strong setups found today.")
        return

    df = pd.DataFrame(results)

    # Sort by Score + R:R
    df = df.sort_values(by=["Score", "R:R"], ascending=False)

    # =========================
    # TERMINAL OUTPUT
    # =========================
    print("\n📊 TOP OPPORTUNITIES:\n")
    print(df.to_string(index=False))

    # =========================
    # EXCEL OUTPUT
    # =========================
    filename = f"Bear_Scan_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    df.to_excel(filename, index=False)

    print(f"\n📁 Saved to {filename}\n")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    run_scanner()