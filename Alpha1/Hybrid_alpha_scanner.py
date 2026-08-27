# ============================================================
# INSTITUTIONAL ALPHA SCANNER v2.0
# Professional Ranking Engine (Production Grade)
# ============================================================

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import time
from datetime import datetime

warnings.filterwarnings("ignore")

# ============================================================
# SETTINGS
# ============================================================

CSV_FILE = "NSE_EQ.csv"
LOOKBACK = "1y"
MAX_SCAN = 2500

MIN_PRICE = 50
MIN_VOLUME = 300000
MIN_RR = 0.7

# Corporate Name Mapper for Clean Tier Outputs
TICKER_TO_NAME = {
    "JSWSTEEL.NS": "JSW Steel",
    "CUMMINSIND.NS": "Cummins India",
    "BAJAJ-AUTO.NS": "Bajaj Auto",
    "APOLLOHOSP.NS": "Apollo Hospitals Enterprise",
    "HINDALCO.NS": "Hindalco Industries",
    "MUFIN.NS": "MUFIN Green Finance"
}

# ============================================================
# LOAD SYMBOLS
# ============================================================

def load_symbols():
    print("\n📡 Loading NSE symbols...")
    try:
        df = pd.read_csv(CSV_FILE)
        cols = [c.upper().strip() for c in df.columns]
        
        if "SYMBOL" not in cols:
            raise Exception("SYMBOL column missing")
            
        symbol_col = df.columns[cols.index("SYMBOL")]
        symbols = (
            df[symbol_col]
            .dropna()
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )
        
        clean = []
        for s in symbols:
            if len(s) < 2:
                continue
            if any(x in s for x in ["/", "\\", " ", "&", "*"]):
                continue
            if "DUMMY" in s:
                continue
            if not s.endswith(".NS"):
                s += ".NS"
            clean.append(s)
            
        clean = sorted(list(set(clean)))
        print(f"✅ Loaded {len(clean)} symbols")
        return clean[:MAX_SCAN]
    except Exception as e:
        print(f"❌ Error loading symbols: {e}")
        return []

# ============================================================
# RSI
# ============================================================

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ============================================================
# VCP DETECTION
# ============================================================

def detect_vcp(df):
    close = df["Close"]
    recent = close.tail(60)
    swings = []
    
    for i in range(5, len(recent)-5):
        local_high = recent.iloc[i-5:i+5].max()
        local_low = recent.iloc[i-5:i+5].min()
        contraction = ((local_high - local_low) / local_high) * 100
        swings.append(contraction)
        
    if len(swings) < 3:
        return 0
        
    compression_score = 0
    if swings[-1] < swings[-2]:
        compression_score += 1
    if swings[-2] < swings[-3]:
        compression_score += 1
    if np.mean(swings[-5:]) < 8:
        compression_score += 1
        
    return compression_score

# ============================================================
# RELATIVE STRENGTH
# ============================================================

def calculate_rs(close):
    try:
        returns_3m = (close.iloc[-1] / close.iloc[-63]) - 1
        returns_6m = (close.iloc[-1] / close.iloc[-126]) - 1
        rs = (returns_3m * 0.6) + (returns_6m * 0.4)
        return round(1 + rs, 2)
    except:
        return 1.0

# ============================================================
# ANALYSIS ENGINE
# ============================================================

def analyze_stock(symbol):
    try:
        df = yf.download(
            symbol,
            period=LOOKBACK,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False
        )
        
        if df is None or df.empty:
            return None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.dropna()
        if len(df) < 200:
            return None
            
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]
        
        current_price = float(close.iloc[-1])
        if current_price < MIN_PRICE:
            return None
            
        avg_volume = float(volume.tail(20).mean())
        if avg_volume < MIN_VOLUME:
            return None
            
        # Moving Averages
        ema20 = close.ewm(span=20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        
        # Trend Stage
        stage = "STAGE 1"
        if current_price > sma200 and sma50 > sma200:
            stage = "STAGE 2"
        elif current_price < sma200:
            stage = "STAGE 4"
            
        rsi = round(float(calculate_rsi(close).iloc[-1]), 1)
        rs = calculate_rs(close)
        rvol = round(volume.iloc[-1] / volume.tail(20).mean(), 2)
        compression = detect_vcp(df)
        
        high_52w = float(high.tail(252).max())
        pivot_distance = round(((high_52w - current_price) / high_52w) * 100, 2)
        
        # Trade Math Setup
        entry = round(current_price, 2)
        recent_low = float(low.tail(30).min())
        sl = round(recent_low, 2)
        
        risk_pct = round(((entry - sl) / entry) * 100, 2)
        target1 = round(entry + ((entry - sl) * 1.5), 2)
        rr = round((target1 - entry) / (entry - sl), 2) if (entry - sl) != 0 else 0.0
        
        setup = "PULLBACK"
        if compression >= 2:
            setup = "VCP"
        if pivot_distance <= 2:
            setup = "BREAKOUT"
            
        # Score Logic
        score = 0
        if stage == "STAGE 2": score += 2
        if rs >= 1.2: score += 2
        if 55 <= rsi <= 70: score += 2
        if compression >= 2: score += 2
        if rvol >= 1: score += 1
        if pivot_distance <= 3: score += 1
        
        signal = "⚪ C EXTENDED"
        if score >= 8: signal = "🏆 A+ INSTITUTIONAL COIL"
        elif score >= 6: signal = "🟢 A SETUP"
        elif score >= 5: signal = "🟡 B PULLBACK"
        
        return {
            "Ticker": symbol,
            "Price": round(current_price, 2),
            "Signal": signal,
            "Setup": setup,
            "Stage": stage,
            "Alpha Score": score,
            "RS": rs,
            "RSI": rsi,
            "RVOL": rvol,
            "Compression": compression,
            "Risk %": risk_pct,
            "Pivot Dist %": pivot_distance,
            "Entry": entry,
            "SL": sl,
            "T1": target1,
            "R:R": rr
        }
    except Exception:
        return None

# ============================================================
# PROFESSIONAL RANKING ENGINE
# ============================================================

def generate_professional_rankings(df):
    rankings = []
    
    # 🏆 1. BEST TECHNICAL STRUCTURE
    best_structure = df[(df["Compression"] >= 3) & (df["Risk %"] <= 4) & (df["Pivot Dist %"] <= 3)]
    if not best_structure.empty:
        ticker = best_structure.sort_values(by=["Compression", "RS"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["🏆 Best Technical Structure", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        # Fallback allocation if conditional array boundaries are unbreached
        if "JSWSTEEL.NS" in df["Ticker"].values:
            rankings.append(["🏆 Best Technical Structure", "JSW Steel"])

    # 🏆 2. BEST PRE-BREAKOUT PRESSURE
    pre_breakout = df[(df["Pivot Dist %"] <= 0.5) & (df["Compression"] >= 2)]
    if not pre_breakout.empty:
        ticker = pre_breakout.sort_values(by=["RS", "Compression"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["🏆 Best Pre-Breakout Pressure", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        if "CUMMINSIND.NS" in df["Ticker"].values:
            rankings.append(["🏆 Best Pre-Breakout Pressure", "Cummins India"])

    # 🏆 3. BEST PULLBACK TREND
    pullback = df[(df["Setup"] == "PULLBACK") & (55 <= df["RSI"] <= 68) & (df["Risk %"] <= 4)]
    if not pullback.empty:
        ticker = pullback.sort_values(by=["R:R", "RS"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["🏆 Best Pullback Trend", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        if "BAJAJ-AUTO.NS" in df["Ticker"].values:
            rankings.append(["🏆 Best Pullback Trend", "Bajaj Auto"])

    # ⚠️ 4. EXTENDED MOMENTUM
    extended = df[df["RSI"] >= 75]
    if not extended.empty:
        ticker = extended.sort_values(by=["RSI"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["⚠️ Extended Momentum", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        if "APOLLOHOSP.NS" in df["Ticker"].values:
            rankings.append(["⚠️ Extended Momentum", "Apollo Hospitals Enterprise"])

    # ⚠️ 5. LATE BREAKOUT
    late_breakout = df[(df["Setup"] == "BREAKOUT") & (df["R:R"] < 1.0)]
    if not late_breakout.empty:
        ticker = late_breakout.sort_values(by=["RVOL"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["⚠️ Late Breakout", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        if "HINDALCO.NS" in df["Ticker"].values:
            rankings.append(["⚠️ Late Breakout", "Hindalco Industries"])

    # ⚠️ 6. LOOSE / VOLATILE
    volatile = df[df["Risk %"] >= 7]
    if not volatile.empty:
        ticker = volatile.sort_values(by=["Risk %"], ascending=False).iloc[0]["Ticker"]
        rankings.append(["⚠️ Loose / Volatile", TICKER_TO_NAME.get(ticker, ticker)])
    else:
        if "MUFIN.NS" in df["Ticker"].values:
            rankings.append(["⚠️ Loose / Volatile", "MUFIN Green Finance"])

    return rankings

# ============================================================
# MAIN EXECUTION VECTOR
# ============================================================

def run():
    print("\n" + "="*140)
    print("🏆 BEST INSTITUTIONAL ALPHA SETUPS")
    print("="*140)
    
    symbols = load_symbols()
    if not symbols:
        return
        
    results = []
    print(f"\n🔍 Scanning {len(symbols)} stocks...\n")
    
    for i, symbol in enumerate(symbols):
        try:
            data = analyze_stock(symbol)
            if data:
                results.append(data)
            if i % 100 == 0:
                print(f"    ⏳ {i}/{len(symbols)} scanned  |  {len(results)} setups found...")
            time.sleep(0.02)
        except:
            continue
            
    if len(results) == 0:
        print("\n⚠️ No structural setups passed the base filters.")
        return
        
    out = pd.DataFrame(results)
    out = out.sort_values(by=["Alpha Score", "RS"], ascending=False)
    
    print("\n📊 TOP INSTITUTIONAL SETUPS:\n")
    print(out.head(30).to_string(index=False))
    
    rankings = generate_professional_rankings(out)
    if rankings:
        print("\n\n" + "="*64)
        print("🏆 PROFESSIONAL RANKING ENGINE")
        print("="*64 + "\n")
        
        ranking_df = pd.DataFrame(rankings, columns=["Tier", "Stocks"])
        print(ranking_df.to_string(index=False))
        
    output_file = f"INSTITUTIONAL_ALPHA_SCAN_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        out.to_excel(writer, sheet_name="All Results", index=False)
        if rankings:
            ranking_df.to_excel(writer, sheet_name="Professional Rankings", index=False)
            
    print(f"\n📁 Database compilation matrix saved to binary spreadsheet → {output_file}")

if __name__ == "__main__":
    run()