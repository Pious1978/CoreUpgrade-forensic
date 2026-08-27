import yfinance as yf
import pandas as pd
import numpy as np

print("🚀 Advanced Pullback Analyzer Started...")

# ============================================
# INPUT
# ============================================
ticker = input("Enter Ticker Name (e.g., TITAN, JSWINFRA, LT): ").upper().strip()

if not ticker.endswith(".NS"):
    ticker += ".NS"

print(f"\n📡 Fetching Data for {ticker}...")

# ============================================
# FETCH DATA
# ============================================
df = yf.download(ticker, period="1y", interval="1d", progress=False)

if df.empty or len(df) < 120:
    print("❌ Not enough data")
    exit()

# ============================================
# FIX MULTIINDEX
# ============================================
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

df = df.dropna().copy()

# ============================================
# SAFE VALUE EXTRACTOR
# ============================================
def val(x):
    if isinstance(x, pd.DataFrame):
        x = x.iloc[:, 0]
    if isinstance(x, pd.Series):
        return float(x.iloc[-1])
    return float(x)

# ============================================
# INDICATORS
# ============================================
df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
df["SMA200"] = df["Close"].rolling(200).mean()

# ATR
high_low = df["High"] - df["Low"]
high_close = np.abs(df["High"] - df["Close"].shift())
low_close = np.abs(df["Low"] - df["Close"].shift())

tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df["ATR"] = tr.rolling(14).mean()

# Volume
df["VolMA20"] = df["Volume"].rolling(20).mean()

# ============================================
# CURRENT VALUES
# ============================================
price = val(df["Close"])

ema20 = val(df["EMA20"])
ema50 = val(df["EMA50"])
sma200 = val(df["SMA200"])

atr = val(df["ATR"])
atr_pct = (atr / price) * 100

avg_vol = val(df["VolMA20"])
current_vol = val(df["Volume"])

rvol = current_vol / avg_vol if avg_vol > 0 else 0

# ============================================
# SWING LEVELS
# ============================================
recent_high = val(df["High"].rolling(50).max())
recent_low = val(df["Low"].rolling(50).min())

support = val(df["Low"].tail(20).min())

fib_618 = recent_high - (recent_high - recent_low) * 0.618

risk_pct = ((price - support) / price) * 100

distance_from_high = ((recent_high - price) / recent_high) * 100

# ============================================
# TREND STRUCTURE
# ============================================
trend_score = 0

# Price structure
if price > ema20:
    trend_score += 1

if ema20 > ema50:
    trend_score += 1

if ema50 > sma200:
    trend_score += 1

if price > sma200:
    trend_score += 1

# EMA slope persistence
ema20_slope = df["EMA20"].iloc[-1] > df["EMA20"].iloc[-5]
ema50_slope = df["EMA50"].iloc[-1] > df["EMA50"].iloc[-5]

if ema20_slope:
    trend_score += 1

if ema50_slope:
    trend_score += 1

# ============================================
# PULLBACK QUALITY
# ============================================
tight_pullback = risk_pct <= 8

healthy_pullback = (
    price > ema50 and
    price > fib_618 and
    risk_pct <= 12
)

# Volume dry-up
recent_vol_5d = df["Volume"].tail(5).mean()

volume_dryup = recent_vol_5d < avg_vol

# ============================================
# COMPRESSION ANALYSIS
# ============================================
recent_range = (
    df["High"].tail(10).max() -
    df["Low"].tail(10).min()
)

range_pct = (recent_range / price) * 100

compression_score = 0

if range_pct < 8:
    compression_score += 2
elif range_pct < 15:
    compression_score += 1

if atr_pct < 3:
    compression_score += 2
elif atr_pct < 5:
    compression_score += 1

if volume_dryup:
    compression_score += 1

# ============================================
# BREAKOUT READINESS
# ============================================
near_high = distance_from_high <= 8

breakout_ready = (
    near_high and
    compression_score >= 3 and
    trend_score >= 5
)

# ============================================
# STRUCTURE CLASSIFICATION
# ============================================
structure = "WEAK"

if trend_score >= 5:
    structure = "STRONG"
elif trend_score >= 3:
    structure = "MODERATE"

# ============================================
# GRADE ENGINE
# ============================================
grade = "C"
verdict = "❌ Avoid"

total_score = 0

# Trend
total_score += trend_score

# Compression
total_score += compression_score

# Pullback quality
if healthy_pullback:
    total_score += 2

if tight_pullback:
    total_score += 2

# RVOL
if rvol > 1.5:
    total_score += 1

# Breakout readiness
if breakout_ready:
    total_score += 2

# ============================================
# FINAL GRADES
# ============================================
if total_score >= 12:
    grade = "A+"
    verdict = "🚀 ELITE PULLBACK"

elif total_score >= 9:
    grade = "A"
    verdict = "🟢 HIGH QUALITY"

elif total_score >= 6:
    grade = "B"
    verdict = "🟡 WATCHLIST"

else:
    grade = "C"
    verdict = "❌ Avoid"

# ============================================
# POSITION SIZING
# ============================================
if grade == "A+":
    position = "Full Position"

elif grade == "A":
    position = "Moderate Position"

elif grade == "B":
    position = "Starter Position"

else:
    position = "No Trade"

# ============================================
# TRADE PLAN
# ============================================
entry = ema20

# Smarter stop
stop = min(
    support,
    ema50 * 0.98
)

risk_per_share = entry - stop

target1 = entry + (risk_per_share * 2)
target2 = entry + (risk_per_share * 3)

rr = (target1 - entry) / risk_per_share if risk_per_share > 0 else 0

# ============================================
# OUTPUT
# ============================================
print("\n===================================================")
print(f"📊 {ticker} ADVANCED TREND ANALYSIS")
print("===================================================")

print(f"💰 Price             : {price:.2f}")

print(f"\n📈 TREND")
print(f"EMA20               : {ema20:.2f}")
print(f"EMA50               : {ema50:.2f}")
print(f"SMA200              : {sma200:.2f}")

print(f"\n🏗️ STRUCTURE")
print(f"Structure           : {structure}")
print(f"Trend Score         : {trend_score}/6")

print(f"\n📦 VOLATILITY")
print(f"ATR                 : {atr:.2f}")
print(f"ATR %               : {atr_pct:.2f}%")
print(f"Compression Score   : {compression_score}/5")

print(f"\n🔊 VOLUME")
print(f"RVOL                : {rvol:.2f}x")

if volume_dryup:
    print("Volume Profile      : 📉 Healthy Pullback")
else:
    print("Volume Profile      : ⚠️ Elevated Activity")

print(f"\n🎯 PULLBACK")
print(f"Support             : {support:.2f}")
print(f"Fib 61.8            : {fib_618:.2f}")
print(f"Risk                : {risk_pct:.2f}%")
print(f"Distance From High  : {distance_from_high:.2f}%")

print("\n===================================================")
print(f"🚦 VERDICT: {verdict}")
print(f"🏅 GRADE   : {grade}")
print(f"⭐ SCORE    : {total_score}")
print("===================================================")

print("\n🧠 LOGIC CHECKLIST")

print(f"{'✅' if price > ema20 else '❌'} Price above EMA20")
print(f"{'✅' if ema20 > ema50 else '❌'} EMA20 above EMA50")
print(f"{'✅' if ema50 > sma200 else '❌'} EMA50 above SMA200")
print(f"{'✅' if healthy_pullback else '❌'} Healthy Pullback")
print(f"{'✅' if volume_dryup else '❌'} Volume Dry-Up")
print(f"{'✅' if breakout_ready else '❌'} Breakout Ready")

print("\n===================================================")
print("📍 TRADE PLAN")
print("===================================================")

print(f"👉 Entry Zone        : {entry:.2f}")
print(f"🛑 Stop Loss         : {stop:.2f}")

print(f"🎯 Target 1          : {target1:.2f}")
print(f"🚀 Target 2          : {target2:.2f}")

print(f"⚖️ Risk/Reward       : {rr:.2f}")
print(f"📦 Position Size     : {position}")

if grade == "C":
    print("\n⚠️ Trade quality too weak. Avoid for now.")

print("===================================================")