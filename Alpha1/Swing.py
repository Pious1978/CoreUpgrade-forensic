import numpy as np
import pandas as pd


# ============================
# VCR CALCULATION
# ============================
def calculate_vcr_tightness(df):
    df = df.copy()

    df["Daily_Range_Pct"] = ((df["High"] - df["Low"]) / df["Close"]) * 100

    recent_vol = df["Daily_Range_Pct"].tail(10).mean()
    historic_vol = df["Daily_Range_Pct"].tail(60).mean()

    if historic_vol == 0 or np.isnan(historic_vol):
        return 1.0

    return recent_vol / historic_vol


# ============================
# SAFE CONVERTER
# ============================
def to_float(x):
    if isinstance(x, pd.Series):
        return float(x.iloc[-1])
    if isinstance(x, pd.DataFrame):
        return float(x.iloc[:, 0].iloc[-1])
    return float(x)


# ============================
# CORE ANALYSIS
# ============================
def analyze_swing(df):

    df = df.dropna().copy()

    if len(df) < 200:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    current_price = to_float(close.iloc[-1])

    ema_50 = to_float(df["Close"].ewm(span=50, adjust=False).mean().iloc[-1])
    ema_200 = to_float(df["Close"].ewm(span=200, adjust=False).mean().iloc[-1])

    # Trend
    is_stage_2 = (current_price > ema_50) and (ema_50 > ema_200)

    # Breakout
    rolling_high_20 = df["Close"].rolling(20).max().iloc[-2]
    is_breakout = current_price > float(rolling_high_20)

    # EMA score
    ema_score = 0
    if current_price > ema_50:
        ema_score += 10
    if current_price > ema_200:
        ema_score += 10

    # VCR
    vcr_score = calculate_vcr_tightness(df)

    trend = "UP" if is_stage_2 else "SIDEWAYS"

    return {
        "trend": trend,
        "breakout": bool(is_breakout),
        "ema_score": int(ema_score),
        "vcr": float(vcr_score),
        "price": float(current_price),
        "ema50": float(ema_50),
        "ema200": float(ema_200),
    }


# ============================
# EXPLANATION LAYER
# ============================
def explain(result):

    if result is None:
        print("❌ No valid result")
        return

    trend = result["trend"]
    breakout = result["breakout"]
    vcr = result["vcr"]
    price = result["price"]

    print("\n" + "=" * 40)
    print("📊 SWING ANALYSIS REPORT")
    print("=" * 40)

    print(f"💰 Price     : {price:.2f}")
    print(f"📈 Trend     : {trend}")
    print(f"🚀 Breakout  : {breakout}")
    print(f"🧊 VCR       : {vcr:.2f}")

    print("\n🧠 INTERPRETATION:")

    if trend == "UP" and vcr < 0.6:
        print("✔️ Strong VCP-style compression setup")
    elif breakout and trend == "SIDEWAYS":
        print("⚠️ Weak structure breakout (risk of failure)")
    elif vcr > 1:
        print("❌ Expansion phase (not a good setup)")
    else:
        print("🟡 Neutral / mixed structure")

    print("\n🎯 ACTION PLAN:")

    if trend == "UP" and breakout:
        print("👉 Watch for pullback entry near EMA20")
    elif breakout:
        print("👉 Wait for retest confirmation")
    else:
        print("👉 Avoid trade / wait for structure improvement")

    print("=" * 40)


# ============================
# MAIN
# ============================
if __name__ == "__main__":

    import yfinance as yf

    ticker = input("Enter ticker (e.g. TATAPOWER.NS): ").strip()

    df = yf.download(ticker, period="1y", interval="1d", progress=False)

    if df is None or df.empty:
        print("❌ No data fetched")
        exit()

    result = analyze_swing(df)

    print("\n📊 RAW RESULT:")
    print(result)

    explain(result)