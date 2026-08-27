# ============================================================
# 🚀 TREND FOLLOWING SCANNER v5.0 (PRO)
# Percentile RS + Advanced VCP + Minervini Trend + Breakout Logic
# ============================================================

import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

# ============================================================
# SETTINGS
# ============================================================

CSV_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\nse_eq.csv"

MAX_WORKERS = 10
TOP_N = 20
LOOKBACK = "18mo"

MIN_PRICE = 50
MIN_AVG_VOLUME = 200000

TARGET_R_MULTIPLE = 3
ATR_PERIOD = 14
ATR_STOP_MULTIPLE = 2.5  # Widened to survive standard momentum shakeouts


# ============================================================
# LOAD SYMBOLS
# ============================================================


def load_symbols():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"❌ File not found: {CSV_PATH}")

    print("📡 Loading NSE EQ symbols...")
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip().upper() for c in df.columns]

    if "SYMBOL" not in df.columns:
        raise Exception("❌ SYMBOL column missing")

    if "SERIES" in df.columns:
        df = df[df["SERIES"] == "EQ"]

    symbols = (
        df["SYMBOL"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
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
        clean.append(s + ".NS")

    print(f"✅ Loaded {len(clean)} symbols")
    return clean


# ============================================================
# TECHNICAL CALCS
# ============================================================


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calculate_raw_rs(stock_close, nifty_close):
    try:
        rs_3m = (stock_close.iloc[-1] / stock_close.iloc[-63]) / (
            nifty_close.iloc[-1] / nifty_close.iloc[-63]
        )
        rs_6m = (stock_close.iloc[-1] / stock_close.iloc[-126]) / (
            nifty_close.iloc[-1] / nifty_close.iloc[-126]
        )
        rs_12m = (stock_close.iloc[-1] / stock_close.iloc[-252]) / (
            nifty_close.iloc[-1] / nifty_close.iloc[-252]
        )
        return rs_3m * 0.4 + rs_6m * 0.3 + rs_12m * 0.3
    except Exception:
        return 0.0


def determine_stage(price, sma50, sma150, sma200):
    if price > sma50 > sma150 > sma200:
        return "Stage 2 ✅"
    elif price < sma50 < sma150 < sma200:
        return "Stage 4 ❌"
    elif price > sma200 and sma50 > sma150:
        return "Stage 2 Early"
    return "Stage 1"


def detect_vcp(df):
    """Deep institutional VCP grading system with 120/80/40/20 windows."""
    try:
        close, volume = df["Close"], df["Volume"]
        contractions = []
        windows = [120, 80, 40, 20]

        for w in windows:
            recent = close.tail(w)
            high, low = recent.max(), recent.min()
            contractions.append(((high - low) / high) * 100)

        layers = sum(
            1
            for i in range(1, len(contractions))
            if contractions[i] < contractions[i - 1]
        )

        vol_120 = volume.tail(120).mean()
        vol_20 = volume.tail(20).mean()
        volume_dryup = (vol_20 / vol_120) < 0.80 if vol_120 else False

        # VCP 10-Point Score
        vcp_score = 0
        if contractions[-1] < contractions[0]:
            vcp_score += 3  # Overall shrinking
        if contractions[-1] < 15:
            vcp_score += 3  # Final contraction quality
        if volume_dryup:
            vcp_score += 2
        vcp_score += min(layers, 2)

        return vcp_score, layers
    except Exception:
        return 0, 0


# ============================================================
# PASS 1: EXTRACT RAW METRICS
# ============================================================


def extract_metrics(symbol, nifty_close):
    """Downloads data and extracts raw technical metrics."""
    try:
        df = yf.download(
            symbol,
            period=LOOKBACK,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        if df.empty or len(df) < 260:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()

        close, high, low, volume = (
            df["Close"],
            df["High"],
            df["Low"],
            df["Volume"],
        )
        price = float(close.iloc[-1])
        if price < MIN_PRICE:
            return None

        # Base Volume: 50-day average EXCLUDING today to avoid self-dilution
        avg_volume_50 = float(volume.iloc[-51:-1].mean())
        if avg_volume_50 < MIN_AVG_VOLUME:
            return None

        # Moving Averages
        sma50 = float(close.rolling(50).mean().iloc[-1])
        sma150 = float(close.rolling(150).mean().iloc[-1])
        sma200 = float(close.rolling(200).mean().iloc[-1])
        sma200_20d_ago = float(close.rolling(200).mean().iloc[-21])

        stage = determine_stage(price, sma50, sma150, sma200)

        # Highs & Lows (Prior to today)
        prior_high_52w = float(high.iloc[-253:-1].max())
        low_52w = float(low.tail(252).min())
        from_high = ((price - prior_high_52w) / prior_high_52w) * 100
        new_high = price > prior_high_52w

        if from_high < -30:
            return None

        # Minervini Trend Template
        cond1 = price > sma50
        cond2 = sma50 > sma150
        cond3 = sma150 > sma200
        cond4 = price > sma200
        cond5 = price >= (prior_high_52w * 0.75)
        cond6 = price >= (low_52w * 1.30)
        cond7 = sma200 > sma200_20d_ago
        trend_template = all(
            [cond1, cond2, cond3, cond4, cond5, cond6, cond7]
        )

        # Raw RS & Breakout Volume
        composite_rs = calculate_raw_rs(close, nifty_close)
        recent_volume = float(volume.iloc[-1])
        relative_volume = recent_volume / avg_volume_50

        # Institutional Pivot (Excluding today)
        pivot = float(high.iloc[-31:-1].max())

        # 10-Day Tightness
        last10 = close.tail(10)
        tight_closes = ((last10.max() - last10.min()) / last10.max()) * 100

        # VCP Score
        vcp_score, layers = detect_vcp(df)

        # Volatility & Momentum
        atr = float(calculate_atr(df, ATR_PERIOD).iloc[-1])
        rsi = float(calculate_rsi(close).iloc[-1])
        if rsi > 92:
            return None

        return {
            "Symbol": str(symbol),
            "Price": round(price, 2),
            "Stage": str(stage),
            "Composite RS": composite_rs,
            "Trend Template": trend_template,
            "VCP Score": vcp_score,
            "VCP Layers": layers,
            "Tight Closes": tight_closes,
            "Rel Volume": round(relative_volume, 2),
            "From 52W High": from_high,
            "New High": new_high,
            "ATR": atr,
            "Pivot": pivot,
        }
    except Exception:
        return None


# ============================================================
# PASS 2: SCORING ENGINE (100-Point Institutional Scale)
# ============================================================


def calculate_score_and_signal(row):
    """Applies a 100-point institutional scoring matrix."""

    # 1. Percentile RS (30 Points)
    rs_percentile = row["RS Rating"]

    # 2. Trend Template (20 Points)
    score_trend = 100 if row["Trend Template"] else 0

    # 3. Proximity to 52W High (15 Points - Reweighted)
    if row["New High"]:
        score_high = 100
    elif row["From 52W High"] >= -2.0:
        score_high = 80
    elif row["From 52W High"] >= -5.0:
        score_high = 60
    elif row["From 52W High"] >= -10.0:
        score_high = 40
    else:
        score_high = 0

    # 4. Breakout Volume Quality (15 Points)
    if row["Rel Volume"] >= 2.0:
        score_vol = 100
    elif row["Rel Volume"] >= 1.5:
        score_vol = 80
    elif row["Rel Volume"] >= 1.2:
        score_vol = 50
    else:
        score_vol = 0

    # 5. Advanced VCP & Tightness Quality (20 Points - Blended)
    vcp_normalized = (row["VCP Score"] / 10) * 100

    # Graded Tightness Module
    tight_val = row["Tight Closes"]
    if tight_val < 2:
        tight_score = 100
    elif tight_val < 4:
        tight_score = 70
    elif tight_val < 6:
        tight_score = 40
    else:
        tight_score = 0

    # Blend VCP shape and recent tightness equally
    score_vcp_tight = (vcp_normalized * 0.5) + (tight_score * 0.5)

    # Weighted Final Score Math
    final_score = (
        (rs_percentile * 0.30)
        + (score_trend * 0.20)
        + (score_vcp_tight * 0.20)
        + (score_vol * 0.15)
        + (score_high * 0.15)
    )

    # Classification Tiers
    if final_score >= 90:
        signal = "🏆 A+ ELITE"
    elif final_score >= 80:
        signal = "🚀 STRONG BUY"
    elif final_score >= 70:
        signal = "✅ WATCHLIST"
    elif final_score >= 60:
        signal = "⚠ EARLY SETUP"
    else:
        signal = "❌ IGNORE"

    return round(final_score, 1), signal


# ============================================================
# MAIN SCANNER & CROSS-SECTIONAL RANKING (PASS 3)
# ============================================================


def run():
    print("\n======================================================")
    print("🚀 TREND FOLLOWING SCANNER v5.0 (PRO)")
    print("Percentile RS + Deep VCP + Minervini + Breakout Logic")
    print("======================================================\n")

    # ---------------------------------------------------------
    # 1. EVALUATE GLOBAL MARKET HEALTH
    # ---------------------------------------------------------
    print("📈 Evaluating NIFTY50 Global Market Health... ", end="")
    nifty = yf.download(
        "^NSEI", period=LOOKBACK, auto_adjust=True, progress=False
    )
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)
    nifty = nifty.dropna()
    nifty_close = nifty["Close"]

    if nifty.empty or len(nifty_close) < 50:
        print("❌ NIFTY data unavailable — rate limited by Yahoo Finance.")
        print("   Wait 60-90 seconds and run again.")
        sys.exit(0)

    nifty_sma50 = nifty_close.rolling(50).mean().iloc[-1]
    nifty_sma200 = nifty_close.rolling(200).mean().iloc[-1]

    market_healthy = (nifty_close.iloc[-1] > nifty_sma50) and (
        nifty_sma50 > nifty_sma200
    )

    if market_healthy:
        print("✅ HEALTHY (Uptrend Confirmed. Standard Execution Mode.)")
    else:
        print(
            "⚠️ DEFENSIVE MODE (Market under pressure. Capital preservation"
            " priority.)"
        )

    # ---------------------------------------------------------
    # 2. PARALLEL DATA EXTRACTION
    # ---------------------------------------------------------
    symbols = load_symbols()
    print(
        f"\n🔍 Extracting raw metrics for {len(symbols)} stocks with"
        f" {MAX_WORKERS} threads...\n"
    )

    raw_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(extract_metrics, symbol, nifty_close): symbol
            for symbol in symbols
        }
        total = len(futures)
        for i, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            if result:
                raw_results.append(result)
            if i % 100 == 0:
                print(
                    f"⏳ {i}/{total} processed | {len(raw_results)} liquid"
                    " candidates..."
                )

    if not raw_results:
        print("\n⚠️ No valid setups found.")
        return

    # ---------------------------------------------------------
    # 3. CROSS-SECTIONAL RANKING & FINAL SCORING
    # ---------------------------------------------------------
    print("\n🧮 Calculating Percentile RS & Institutional Scores...")
    df = pd.DataFrame(raw_results)

    # Calculate TRUE Percentile RS (kept strictly numeric)
    df["RS Rating"] = (df["Composite RS"].rank(pct=True) * 100).astype(int)

    # Apply Scoring
    df[["Score", "Signal"]] = df.apply(
        lambda row: pd.Series(calculate_score_and_signal(row)), axis=1
    )

    # Remove Weak Candidates
    df = df[df["Signal"] != "❌ IGNORE"].copy()

    # Calculate Entry & Risk metrics
    df["Entry"] = round(df["Pivot"] * 1.002, 2)
    df["SL"] = round(df["Entry"] - (df["ATR"] * ATR_STOP_MULTIPLE), 2)
    df["Risk %"] = round(((df["Entry"] - df["SL"]) / df["Entry"]) * 100, 2)

    # Filter out absurd risk
    df = df[df["Risk %"] <= 15]

    df["Target 1"] = round(
        df["Entry"] + ((df["Entry"] - df["SL"]) * TARGET_R_MULTIPLE), 2
    )
    df["R:R"] = round(
        (df["Target 1"] - df["Entry"]) / (df["Entry"] - df["SL"]), 2
    )

    # Clean Data Formatting
    df.rename(
        columns={
            "From 52W High": "From 52W High %",
            "Tight Closes": "Tight Closes %",
        },
        inplace=True,
    )
    df["From 52W High %"] = df["From 52W High %"].round(2)
    df["Tight Closes %"] = df["Tight Closes %"].round(2)
    df["Trend Template"] = np.where(df["Trend Template"], "✅ Met", "❌ Fail")

    # Clean and sort final dataframe
    final_cols = [
        "Symbol",
        "Price",
        "Stage",
        "Trend Template",
        "RS Rating",
        "VCP Score",
        "Tight Closes %",
        "Rel Volume",
        "From 52W High %",
        "Entry",
        "SL",
        "Risk %",
        "Target 1",
        "R:R",
        "Score",
        "Signal",
    ]

    # Primary Sort: Institutional Score -> RS Rating
    df = df.sort_values(by=["Score", "RS Rating"], ascending=False)
    out = df[final_cols]

    # ---------------------------------------------------------
    # 4. OUTPUT SUMMARY
    # ---------------------------------------------------------
    elite_setups = out[out["Signal"] == "🏆 A+ ELITE"]
    strong_buy = out[out["Signal"] == "🚀 STRONG BUY"]
    watchlist = out[out["Signal"] == "✅ WATCHLIST"]
    early_setups = out[out["Signal"] == "⚠ EARLY SETUP"]

    print("\n======================================================")
    print("📊 SCAN RESULTS SUMMARY")
    print("======================================================")
    print(f"🏆 A+ Elite Setups: {len(elite_setups)}")
    print(f"🚀 Strong Buys    : {len(strong_buy)}")
    print(f"✅ Watchlist      : {len(watchlist)}")
    print(f"⚠ Early Setups    : {len(early_setups)}")
    print(f"📦 Total Approved : {len(out)}")

    if not elite_setups.empty:
        print("\n🏆 A+ ELITE SETUPS:\n")
        print(elite_setups.head(TOP_N).to_string(index=False))
    elif not strong_buy.empty:
        print("\n🚀 STRONG BUYS:\n")
        print(strong_buy.head(TOP_N).to_string(index=False))

    # SAVE TO EXCEL
    filename = f"Pro_Trend_Scan_v5_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    with pd.ExcelWriter(filename) as writer:
        out.to_excel(writer, sheet_name="All Setups", index=False)
        if not elite_setups.empty:
            elite_setups.to_excel(writer, sheet_name="Elite", index=False)
        if not strong_buy.empty:
            strong_buy.to_excel(writer, sheet_name="Strong Buy", index=False)
        if not watchlist.empty:
            watchlist.to_excel(writer, sheet_name="Watchlist", index=False)

    print(f"\n📁 Results saved → {filename}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    start = time.time()
    run()
    end = time.time()
    print(f"\n⏱️ Scan completed in {round(end - start, 2)} seconds\n")