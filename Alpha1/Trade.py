import pandas as pd
import numpy as np
import yfinance as yf

PORTFOLIO_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\Stocks_Holdings_Statement.xlsx"
NIFTY_SYMBOL = "^NSEI"


# =========================
# LOAD PORTFOLIO
# =========================
def load_portfolio():
    try:
        df = pd.read_excel(PORTFOLIO_PATH)
        df.columns = [c.strip() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

portfolio = load_portfolio()


# =========================
# CANONICAL NORMALIZER (KEY FIX)
# =========================
def canonical(x):
    x = str(x).upper()

    x = x.replace("&", " AND ")
    x = x.replace(".", " ")
    x = x.replace("-", " ")

    # remove corporate suffix noise
    for w in ["LIMITED", "LTD", "PVT", "PRIVATE", "COMPANY", "CO"]:
        x = x.replace(w, "")

    return " ".join(x.split()).strip()


# =========================
# MARKET DATA
# =========================
def get_market():
    try:
        df = yf.Ticker(NIFTY_SYMBOL).history(period="6mo")
        # --- FIX 1: Flatten MultiIndex column index patterns ---
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # --- FIX 2: Clear any incomplete placeholder or live NaN rows ---
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        return df
    except:
        return None


# =========================
# HOLDING CHECK (FINAL FIXED VERSION)
# =========================
def check_holding(symbol_used):

    if portfolio.empty:
        return False, None

    col = "Stock Name"
    if col not in portfolio.columns:
        return False, None

    # canonical portfolio names
    df_col = portfolio[col].astype(str).apply(canonical)

    # NOTE: we still use Yahoo only as optional enrichment (NOT identity)
    try:
        long_name = yf.Ticker(symbol_used).info.get("longName", "")
    except:
        long_name = ""

    long_name = canonical(long_name)

    # =========================
    # DEBUG (keep until stable)
    # =========================
    print("\n[DEBUG]")
    print("Yahoo Name:", long_name)
    print("Portfolio Sample:", df_col.head(5).tolist())

    # =========================
    # MATCH STRATEGY 1: FULL CANONICAL MATCH
    # =========================
    if long_name:
        mask = df_col.str.contains(long_name, na=False)
        if mask.any():
            row = portfolio[mask]
            return True, row.iloc[0].get("Average buy price", None)

    # =========================
    # MATCH STRATEGY 2: TOKEN OVERLAP MATCH (ROBUST BACKUP)
    # =========================
    if long_name:
        tokens = [t for t in long_name.split() if len(t) > 3]

        for t in tokens:
            mask = df_col.str.contains(t, na=False)
            if mask.any():
                row = portfolio[mask]
                return True, row.iloc[0].get("Average buy price", None)

    return False, None


# =========================
# NORMALIZE SYMBOL INPUT
# =========================
def normalize(t):
    t = t.upper().strip()
    if ".NS" in t or ".BO" in t:
        return [t]
    return [t + ".NS", t + ".BO", t]


# =========================
# FETCH DATA
# =========================
def fetch(tlist):
    for t in tlist:
        try:
            df = yf.Ticker(t).history(period="2y")
            if df is not None and len(df) > 100:
                # --- FIX 1: Flatten MultiIndex column structures ---
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                # --- FIX 2: Evict trailing partial candles or NaN rows ---
                df = df.dropna(subset=["Open", "High", "Low", "Close"])
                return df, t
        except:
            continue
    return None, None


# =========================
# ANALYSIS ENGINE
# =========================
def analyze(df, market):

    close = df["Close"]

    c = close.iloc[-1]
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    h60 = df["High"].rolling(60).max().iloc[-1]
    l60 = df["Low"].rolling(60).min().iloc[-1]

    vr = df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1]

    rs = close.pct_change(20).iloc[-1]

    mclose = market["Close"]
    rs_mkt = mclose.pct_change(20).iloc[-1]

    rs_rel = rs - rs_mkt

    trend = "UP" if ema20 > ema50 else "SIDEWAYS"

    tight = 1 / ((df["High"] - df["Low"]) / close).rolling(20).mean().iloc[-1]

    m_ema50 = mclose.ewm(span=50).mean().iloc[-1]
    m_ema200 = mclose.ewm(span=200).mean().iloc[-1]

    if m_ema50 > m_ema200 and rs_mkt > 0:
        regime = "STRONG_BULL"
    elif m_ema50 > m_ema200:
        regime = "WEAK_BULL"
    else:
        regime = "RISK_OFF"

    return c, ema20, ema50, h60, l60, vr, rs, rs_rel, trend, tight, regime


# =========================
# TRADE PLAN (RISK ENGINE REPAIRED)
# =========================
def plan(c, e20, e50, h60, df):

    low = round(min(e20, e50) * 0.98, 2)
    high = round(max(e20, e50) * 1.01, 2)

    breakout = round(h60 * 1.01, 2)

    # --- FIX: Structural Risk Wrap instead of 60-day trailing leak ---
    l15 = df["Low"].tail(15).min()
    sl_structural = min(e50, l15)
    sl_floor = e50 * 0.96  # Protective volatility floor cap at ~4% below 50 EMA

    sl = round(max(sl_structural, sl_floor), 2)

    t1 = round(c * 1.08, 2)
    t2 = round(h60 * 1.15, 2)

    # Prevent potential ZeroDivisionErrors if stop parameters compress to equivalence
    rr = round((t2 - c) / (c - sl), 2) if (c - sl) != 0 else 0

    return low, high, breakout, sl, t1, t2, rr


# =========================
# SIGNAL
# =========================
def signal(score):

    if score >= 75:
        return "🔥 HIGH CONVICTION BUY"
    elif score >= 60:
        return "🟢 ACCUMULATE"
    elif score >= 45:
        return "🟡 WATCH"
    else:
        return "🔴 AVOID"


# =========================
# MAIN
# =========================
def run():

    raw = input("\n📌 Enter Stock: ")
    tlist = normalize(raw)

    df, used = fetch(tlist)

    if df is None:
        print("❌ No data found")
        return

    market = get_market()
    if market is None:
        print("❌ Error fetching global market reference indices")
        return

    holding, avg = check_holding(used)

    c, e20, e50, h60, l60, vr, rs, rs_rel, trend, tight, regime = analyze(df, market)

    # Pass the full df down to compute the tight structural low metrics
    low, high, brk, sl, t1, t2, rr = plan(c, e20, e50, h60, df)

    score = 50  # placeholder (your edge engine already exists)

    sig = signal(score)

    print("\n" + "="*60)
    print(f"📊 {used}")
    print("="*60)

    print(f"💰 Price: {c}")
    print(f"📈 Trend: {trend}")
    print(f"🌍 Market Regime: {regime}")

    print(f"\n📍 ENTRY")
    print(f"{low} - {high}")
    print(f"Breakout: {brk}")

    print(f"\n🛑 RISK")
    print(f"SL: {sl}")
    print(f"T1: {t1}")
    print(f"T2: {t2}")
    print(f"RR: {rr}")

    print(f"\n📦 HOLDING: {holding}")
    if holding:
        print("Avg Price:", avg)

    print(f"\n🚦 SIGNAL: {sig}")
    print("="*60)


if __name__ == "__main__":
    run()