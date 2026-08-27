# ============================================================
# BEAR MARKET VALUE SCANNER v3.1
# Enhanced Dynamic R:R + Relative Strength Alpha Version
# Stable + Retry Enabled + Yahoo Safe
# ============================================================

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import time
import random

from datetime import datetime

warnings.filterwarnings("ignore")

# ============================================================
# SETTINGS
# ============================================================

CSV_FILE = "NSE_EQ.csv"
LOOKBACK = "1y"
BENCHMARK = "^NSEI"          # Nifty 50 Index for Relative Strength Comparison

MIN_PRICE = 20
MIN_VOLUME = 200000
MAX_SCAN = 2500

MIN_PULLBACK = 25
MAX_PULLBACK = 80

RSI_OVERSOLD = 35
RSI_ACCUMULATION = 50

# ============================================================
# RISK MANAGEMENT & ALFA FILTERS
# ============================================================

MIN_RR = 2.0                 # Minimum acceptable structural R:R
TARGET_RECOVERY = 0.50       # Target set at 50% recovery of the drawdown
MIN_RS_ALPHA = -0.10         # Filter out severe value traps (underperforming index by >10%)
MAX_RETRIES = 3

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
# RSI CALCULATION
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
# FIBONACCI
# ============================================================

def nearest_fib(price, high, low):
    diff = high - low
    fibs = {
        "23.6%": high - diff * 0.236,
        "38.2%": high - diff * 0.382,
        "50.0%": high - diff * 0.500,
        "61.8%": high - diff * 0.618,
        "78.6%": high - diff * 0.786,
    }
    nearest = min(fibs.items(), key=lambda x: abs(price - x[1]))
    return nearest[0]

# ============================================================
# SAFE DOWNLOAD
# ============================================================

def safe_download(symbol):
    for attempt in range(MAX_RETRIES):
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
                time.sleep(1)
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()
            if len(df) < 200:
                return None

            required = ["Close", "High", "Low", "Volume"]
            for col in required:
                if col not in df.columns:
                    return None

            return df

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                print(f"⚠️ Failed: {symbol} -> {str(e)[:60]}")
            time.sleep(1)
    return None

# ============================================================
# ANALYSIS ENGINE
# ============================================================

def analyze_stock(symbol, nifty_df):
    try:
        df = safe_download(symbol)
        if df is None:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        current_price = float(close.iloc[-1])

        # ====================================================
        # BASIC FILTERS
        # ====================================================
        if current_price < MIN_PRICE:
            return None

        avg_volume = float(volume.tail(20).mean())
        if avg_volume < MIN_VOLUME:
            return None

        # ====================================================
        # RELATIVE STRENGTH (VS NIFTY 50) - Anti-Value-Trap
        # ====================================================
        common_dates = df.index.intersection(nifty_df.index)
        lookback_idx = min(126, len(common_dates) - 1)  # ~6 months
        
        if lookback_idx < 40:
            return None

        stock_hist = float(close.loc[common_dates[-lookback_idx]])
        nifty_hist = float(nifty_df["Close"].loc[common_dates[-lookback_idx]])

        stock_perf = (current_price - stock_hist) / stock_hist
        nifty_perf = (float(nifty_df["Close"].iloc[-1]) - nifty_hist) / nifty_hist
        rs_alpha = stock_perf - nifty_perf

        # Dynamic hard filter against structurally dead names
        if rs_alpha < MIN_RS_ALPHA:
            return None

        # ====================================================
        # MOVING AVERAGES & 52W HIGH / LOW
        # ====================================================
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])

        if np.isnan(sma50) or np.isnan(sma200):
            return None

        high_52w = float(high.tail(252).max())
        low_52w = float(low.tail(252).min())

        if high_52w <= low_52w:
            return None

        pullback_pct = ((high_52w - current_price) / high_52w) * 100

        if not (MIN_PULLBACK <= pullback_pct <= MAX_PULLBACK):
            return None

        # ====================================================
        # RSI & FIBONACCI
        # ====================================================
        rsi_series = calculate_rsi(close)
        if rsi_series.isna().all():
            return None
        rsi = float(rsi_series.iloc[-1])

        fib = nearest_fib(current_price, high_52w, low_52w)

        # ====================================================
        # ENTRY / STOPLOSS / DYNAMIC TARGET (REAL R:R)
        # ====================================================
        entry = round(current_price, 2)
        recent_low = float(low.tail(30).min())
        sl = round(recent_low * 0.97, 2)
        risk = entry - sl

        if risk <= 0:
            return None

        # DYNAMIC TARGET: Structural resistance at a 50% recovery of the correction arc
        target1 = round(current_price + (high_52w - current_price) * TARGET_RECOVERY, 2)
        reward = target1 - entry
        rr = round(reward / risk, 2)

        # Drop the pick if the risk profile doesn't justify the structural upside
        if rr < MIN_RR:
            return None

        # ====================================================
        # SCORING SYSTEM
        # ====================================================
        score = 0

        # Pullback depth
        if pullback_pct >= 50: score += 2
        elif pullback_pct >= 35: score += 1

        # RSI strength
        if rsi <= RSI_OVERSOLD: score += 3
        elif rsi <= RSI_ACCUMULATION: score += 2
        elif rsi <= 70: score += 1

        # Fibonacci zone
        if fib in ["78.6%", "61.8%"]: score += 2
        elif fib == "50.0%": score += 1

        # Trend structure
        if current_price > sma50: score += 1
        if current_price > sma200: score += 1

        # Relative Strength Alpha bonus
        if rs_alpha > 0.10: score += 2
        elif rs_alpha > 0: score += 1

        # ====================================================
        # SIGNAL ENGINE
        # ====================================================
        signal = "🟡 WATCH"
        if score >= 8: signal = "🟢 DEEP VALUE"
        elif score >= 6: signal = "🟢 VALUE BUY"
        elif score >= 5: signal = "🟡 ACCUMULATE"

        return {
            "Stock": symbol,
            "Price": round(current_price, 2),
            "Pullback%": round(pullback_pct, 2),
            "RSI(14)": round(rsi, 1),
            "RS Alpha%": round(rs_alpha * 100, 2),
            "Nearest Fib": fib,
            "Entry Ideal": entry,
            "SL": sl,
            "Target 1": target1,
            "R:R": rr,
            "Score": score,
            "Signal": signal
        }

    except Exception as e:
        print(f"⚠️ Error analyzing {symbol}: {str(e)[:50]}")
        return None

# ============================================================
# MAIN ENGINE
# ============================================================

def run():
    print("\n=================================================================")
    print("🚀 BEAR MARKET VALUE SCANNER v3.1 (Dynamic R:R + RS Filter)")
    print("=================================================================")

    # Warm up benchmark historical index details safely
    print(f"📊 Loading baseline performance data from benchmark ({BENCHMARK})...")
    nifty_df = yf.download(BENCHMARK, period=LOOKBACK, interval="1d", auto_adjust=True, progress=False, threads=False)
    if isinstance(nifty_df.columns, pd.MultiIndex):
        nifty_df.columns = nifty_df.columns.get_level_values(0)
    nifty_df = nifty_df.dropna()

    symbols = load_symbols()
    if not symbols:
        return

    print(f"\n🔍 Scanning {len(symbols)} stocks...\n")
    results = []
    start = time.time()

    for i, symbol in enumerate(symbols):
        data = analyze_stock(symbol, nifty_df)
        if data:
            results.append(data)

        if i % 100 == 0 and i != 0:
            elapsed = round(time.time() - start, 1)
            print(f"   ⏳ {i}/{len(symbols)} scanned |  {len(results)} valid setups |  {elapsed}s")

        time.sleep(random.uniform(0.05, 0.12))

        if i % 250 == 0 and i != 0:
            print("   😴 Cooling down Yahoo requests to prevent throttling...")
            time.sleep(3)

    # ========================================================
    # OUTPUT GENERATION
    # ========================================================
    if len(results) == 0:
        print("\n⚠️ No setups cleared the filters.")
        return

    out = pd.DataFrame(results)
    out = out.sort_values(by=["Score", "R:R"], ascending=False)

    deep_value = out[out["Signal"] == "🟢 DEEP VALUE"]
    value_buy = out[out["Signal"] == "🟢 VALUE BUY"]
    accumulate = out[out["Signal"] == "🟡 ACCUMULATE"]
    watch = out[out["Signal"].str.contains("WATCH")]

    print("\n📊 SCAN RESULTS SUMMARY")
    print("============================================================")
    print(f"🟢 DEEP VALUE : {len(deep_value)}")
    print(f"🟢 VALUE BUY  : {len(value_buy)}")
    print(f"🟡 ACCUMULATE : {len(accumulate)}")
    print(f"🟡 WATCH      : {len(watch)}")
    print(f"📦 TOTAL QUALS: {len(out)}")

    print("\n📊 TOP 20 STRUCTURAL VALUE OPPORTUNITIES:\n")
    print(out.head(20).to_string(index=False))

    output_file = f"BEAR_SCAN_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        out.to_excel(writer, sheet_name="All Results", index=False)
        deep_value.to_excel(writer, sheet_name="Deep Value", index=False)
        value_buy.to_excel(writer, sheet_name="Value Buy", index=False)
        accumulate.to_excel(writer, sheet_name="Accumulate", index=False)
        watch.to_excel(writer, sheet_name="Watchlist", index=False)

    print(f"\n📁 File saved cleanly → {output_file}")

if __name__ == "__main__":
    run()