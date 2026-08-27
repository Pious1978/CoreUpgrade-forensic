import pandas as pd
import numpy as np
import yfinance as yf

# =========================================================
# CONFIG & LOAD
# =========================================================
PORTFOLIO_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\Stocks_Holdings_Statement.xlsx"
NIFTY = "^NSEI"

def load_portfolio():
    try:
        df = pd.read_excel(PORTFOLIO_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    except: return pd.DataFrame()

portfolio = load_portfolio()

# =========================================================
# HELPERS
# =========================================================
def canonical(x):
    x = str(x).upper()
    for w in ["LIMITED","LTD","PVT","PRIVATE","COMPANY","CO"]: x = x.replace(w,"")
    return " ".join(x.split()).strip()

def normalize_symbol(symbol):
    symbol = symbol.upper().strip()
    return [symbol] if symbol.endswith((".NS", ".BO")) else [symbol+".NS", symbol+".BO", symbol]

def get_market():
    try:
        df = yf.Ticker(NIFTY).history(period="1y")
        return df if not df.empty and len(df) >= 100 else None
    except: return None

def market_regime(market):
    if market is None: return "UNKNOWN"
    ema50 = market["Close"].ewm(span=50).mean().iloc[-1]
    ema200 = market["Close"].ewm(span=200).mean().iloc[-1]
    return "BULL" if ema50 > ema200 else "RISK_OFF"

def distribution_days(market):
    if market is None: return 0
    close, vol, dd = market["Close"], market["Volume"], 0
    for i in range(-10, -1):
        if close.iloc[i] < close.iloc[i-1] and vol.iloc[i] > vol.iloc[i-1]: dd += 1
    return dd

# =========================================================
# ENGINE LOGIC
# =========================================================
def tech_engine(df, market):
    if df is None: return 0
    ema20, ema50 = df["Close"].ewm(span=20).mean().iloc[-1], df["Close"].ewm(span=50).mean().iloc[-1]
    trend = 25 if ema20 > ema50 else 0
    rs = (df["Close"].pct_change(20).iloc[-1] - market["Close"].pct_change(20).iloc[-1]) * 200
    return trend + np.clip(rs, 0, 25)

def fund_score(symbol):
    try:
        i = yf.Ticker(symbol).info
        f = {"roe": i.get("returnOnEquity",0) or 0, "debt": i.get("debtToEquity",0) or 0, 
             "margin": i.get("profitMargins",0) or 0, "growth": i.get("revenueGrowth",0) or 0}
        s = (30 if f["roe"] > 0.15 else 0) + (20 if f["debt"] < 1 else 0) + \
            (20 if f["margin"] > 0.15 else 0) + (30 if f["growth"] > 0.1 else 0)
        return min(s, 100)
    except: return 0

def plan(df):
    c = df["Close"].iloc[-1]
    h60, l15 = df["High"].rolling(60).max().iloc[-1], df["Low"].rolling(15).min().iloc[-1]
    sl = min(l15, df["Close"].ewm(span=50).mean().iloc[-1])
    rr = (h60 * 1.15 - c) / (c - sl) if c > sl else 0
    return c, sl, rr

def signal(setup_score, regime, rr):
    if rr < 1.5: return "🔴 AVOID (Poor RR)"
    base = "🔥 HIGH CONVICTION" if setup_score >= 70 else "🟢 ACCUMULATE" if setup_score >= 50 else "🟡 WATCH"
    return f"{base} (REDUCED SIZE - RISK_OFF)" if regime == "RISK_OFF" else base

def position_size(df, regime, setup_score, rr):
    if df is None or rr < 1.5: return 0.0
    vol = df["Close"].pct_change().std()
    size = (0.20 / (1 + vol)) * (0.3 if regime == "RISK_OFF" else 1.0)
    return round(max(0.01, size * min(1.0, setup_score / 80)), 4)

# =========================================================
# RUNNER
# =========================================================
def run():
    symbol = input("Enter Stock Symbol: ").upper().strip()
    market = get_market()
    regime = market_regime(market)
    
    for sym in normalize_symbol(symbol):
        df = yf.Ticker(sym).history(period="2y")
        if not df.empty and len(df) >= 120:
            c, sl, rr = plan(df)
            ts, fs = tech_engine(df, market), fund_score(sym)
            score = ts * 0.6 + fs * 0.4
            
            print(f"\n{'='*25}\n{sym} | Regime: {regime}\n{'='*25}")
            print(f"Signal: {signal(score, regime, rr)}")
            print(f"Size: {position_size(df, regime, score, rr)*100:.2f}%")
            print(f"Price: {c:.2f} | SL: {sl:.2f} | RR: {rr:.2f}")
            break
    else: print("❌ No valid data found.")

if __name__ == "__main__":
    run()