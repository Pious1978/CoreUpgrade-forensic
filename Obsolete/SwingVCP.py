# =========================================
# 📊 SWING VCP ANALYZER (DEBUG SAFE)
# =========================================

import numpy as np
import pandas as pd
import yfinance as yf


print("🚀 Script Started...")  # <-- DEBUG CONFIRM


# ============================
# VCR CALCULATION
# ============================
def calculate_vcr_tightness(df):
    df = df.copy()

    df['Daily_Range_Pct'] = ((df['High'] - df['Low']) / df['Close']) * 100

    recent_vol = df['Daily_Range_Pct'].tail(10).mean()
    historic_vol = df['Daily_Range_Pct'].tail(60).mean()

    if historic_vol == 0 or np.isnan(historic_vol):
        return 1.0

    return recent_vol / historic_vol


# ============================
# CORE VCP ANALYSIS
# ============================
def analyze_vcp(df):

    if df is None or df.empty:
        print("❌ Empty DataFrame")
        return None

    # FIX: flatten columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna().copy()

    print(f"📊 Data Length: {len(df)}")

    if len(df) < 200:
        print("⚠️ Not enough candles (need 200)")
        return None

    try:
        current_price = float(df['Close'].iloc[-1])
        ema_50 = float(df['Close'].ewm(span=50).mean().iloc[-1])
        ema_200 = float(df['Close'].ewm(span=200).mean().iloc[-1])

        high_52 = float(df['High'].rolling(252).max().iloc[-1])

        vcr_score = calculate_vcr_tightness(df)

        is_stage_2 = (current_price > ema_50) and (ema_50 > ema_200)
        is_near_pivot = current_price >= (high_52 * 0.93)

        compression_score = 0

        if vcr_score < 0.60:
            compression_score += 8
        elif vcr_score < 0.75:
            compression_score += 4

        if is_stage_2:
            compression_score += 5

        if is_near_pivot:
            compression_score += 5

        compression_score = min(compression_score, 15)

        return {
            "compression_score": int(compression_score),
            "vcr": round(float(vcr_score), 2),
            "near_pivot": bool(is_near_pivot)
        }

    except Exception as e:
        print(f"❌ Calculation Error: {e}")
        return None


# ============================
# MAIN EXECUTION (FORCED RUN)
# ============================
try:
    ticker = input("Enter stock (e.g. TATAPOWER.NS): ").strip()

    print(f"\n📡 Fetching data for {ticker}...")

    df = yf.download(ticker, period="1y", interval="1d", progress=False)

    if df is None or df.empty:
        print("❌ Failed to fetch data")
    else:
        result = analyze_vcp(df)

        if result:
            print("\n📊 VCP RESULT:\n")
            print(result)
        else:
            print("⚠️ No valid result")

except Exception as e:
    print(f"🔥 SCRIPT ERROR: {e}")