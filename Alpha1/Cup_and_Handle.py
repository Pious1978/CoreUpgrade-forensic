# =============================================================================
# 🚀 INSTITUTIONAL CUP & HANDLE SCANNER (V3 - MULTI-FACTOR QUANT MATRIX)
# Continuous Volume/OBV + Multi-Horizon RS + Smooth Stage2 + Granular Diagnostics
# =============================================================================

import os
import sys
import time
import logging
import warnings
from datetime import datetime
import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ==============================
# SYSTEM CONFIGURATION
# ==============================
CSV_FILE = "NSE_EQ.csv"
LOOKBACK = "1y"
MAX_SCAN = 2500
NIFTY_SYMBOL = "^NSEI"
BATCH_SIZE = 100

FORCE_FULL_UNIVERSE = True

# ==============================
# THRESHOLDS & PARAMETERS
# ==============================
HANDLE_RIM_PCT = 0.12          # Handle must sit within upper 12% of base
MIN_DAYS_IN_BASE_BOTTOM = 15   # Minimum sessions in base floor (U-shape check)
BASE_BOTTOM_ZONE_PCT = 0.30    # Bottom 30% price range of the base
MIN_DAILY_TURNOVER = 3e7       # ₹3 Crore minimum avg daily traded value


# ==============================
# UNIVERSE HELPERS
# ==============================
def is_weekend():
    return datetime.now().weekday() >= 5


def load_symbols_full():
    if not os.path.exists(CSV_FILE):
        print(f"⚠️ {CSV_FILE} not found in directory!")
        return []
    
    df = pd.read_csv(CSV_FILE)
    if "SYMBOL" not in df.columns:
        print(f"⚠️ No 'SYMBOL' column in {CSV_FILE}!")
        return []
        
    symbols = df["SYMBOL"].dropna().astype(str).str.upper().tolist()
    dead_symbols = {"GATI", "LTIM", "JSWCEMENT", "PIRAMALFIN"}
    symbols = [s for s in symbols if s not in dead_symbols]

    clean_list = list(
        set([
            s.strip() + ".NS" if not s.strip().endswith(".NS") else s.strip()
            for s in symbols
        ])
    )[:MAX_SCAN]
    print(f"✅ Loaded {len(clean_list)} symbols from {CSV_FILE}.")
    return clean_list


def load_nifty_reference(session):
    try:
        nifty = yf.download(NIFTY_SYMBOL, period=LOOKBACK, interval="1d", progress=False, session=session)
        if nifty is None or nifty.empty:
            return None
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty = nifty['Close']
            if isinstance(nifty, pd.DataFrame):
                nifty = nifty.iloc[:, 0]
        else:
            nifty = nifty['Close']
        return nifty.dropna()
    except Exception as e:
        print(f"⚠️ Nifty fetch failed: {e}")
        return None


# ==============================
# 1. MULTI-HORIZON RELATIVE STRENGTH
# ==============================
def calculate_blended_excess_return(df, nifty_s):
    """
    Blended Excess Return vs Nifty across 3 horizons:
    - 3 Month (63 trading days)  : 40% Weight
    - 6 Month (126 trading days) : 35% Weight
    - 12 Month (252 trading days): 25% Weight
    """
    if nifty_s is None or len(df) < 252 or len(nifty_s) < 252:
        return None
    try:
        horizons = [(63, 0.40), (126, 0.35), (252, 0.25)]
        blended_excess = 0.0

        for days, weight in horizons:
            stock_past_price = df["Close"].iloc[-days]
            stock_ret = (df["Close"].iloc[-1] / stock_past_price) - 1.0

            target_date = df.index[-days]
            nifty_past = nifty_s.loc[nifty_s.index >= target_date]
            if nifty_past.empty:
                return None
            nifty_ret = (nifty_s.iloc[-1] / nifty_past.iloc[0]) - 1.0

            blended_excess += (stock_ret - nifty_ret) * weight

        return float(blended_excess)
    except:
        return None


# ==============================
# 2. SMOOTH STAGE 2 & TREND MATRIX (15 PTS MAX)
# ==============================
def calculate_trend_score(df):
    """
    Evaluates 6 trend sub-components instead of a binary jump:
    - EMA 50 > EMA 150
    - EMA 150 > EMA 200
    - Price > EMA 50
    - Price > EMA 200
    - EMA 200 Slope > 0 (Rising)
    - Dist to 52W High >= 85%
    """
    close = df["Close"]
    ema50 = close.ewm(span=50).mean()
    ema150 = close.ewm(span=150).mean()
    ema200 = close.ewm(span=200).mean()

    p = float(close.iloc[-1])
    e50 = float(ema50.iloc[-1])
    e150 = float(ema150.iloc[-1])
    e200 = float(ema200.iloc[-1])
    e200_slope = e200 - float(ema200.iloc[-20])
    h52 = float(df["High"].tail(252).max())

    points = 0
    if e50 > e150: points += 2.5
    if e150 > e200: points += 2.5
    if p > e50: points += 2.5
    if p > e200: points += 2.5
    if e200_slope > 0: points += 2.5
    if (p / h52) >= 0.85: points += 2.5

    return min(points, 15.0)


# ==============================
# 3. CONTINUOUS VOLUME & OBV SCORE (20 PTS MAX)
# ==============================
def calculate_volume_score(df):
    """
    Uses continuous metrics instead of flags:
    - Handle Dry-Up Ratio (Volume in handle vs right-side rim)
    - Right-Side Volume Expansion Ratio (Right rim vs Left rim volume)
    - Current RVOL (1-day Vol vs 20-day Vol)
    - OBV Slope (20-day linear trend of On-Balance Volume)
    """
    window = df.tail(135)
    if len(window) < 135:
        return 0.0, 0.0, 0.0

    handle = window.tail(15)
    cup_body = window.iloc[:-15]
    left_rim = cup_body.head(30)
    right_rim = cup_body.tail(30)

    # 1. Dry-Up Ratio
    right_rim_vol = right_rim["Volume"].mean() + 1e-9
    handle_vol = handle["Volume"].mean()
    dryup_ratio = handle_vol / right_rim_vol

    dryup_score = 0.0
    if dryup_ratio <= 0.50: dryup_score = 6.0
    elif dryup_ratio <= 0.70: dryup_score = 4.0
    elif dryup_ratio <= 0.85: dryup_score = 2.0

    # 2. Right-Side Volume Expansion
    left_rim_vol = left_rim["Volume"].mean() + 1e-9
    expansion_ratio = right_rim_vol / left_rim_vol
    expansion_score = min((expansion_ratio / 1.5) * 5.0, 5.0)

    # 3. RVOL (Relative Volume on recent session)
    rvol = float(df["Volume"].iloc[-1]) / float(df["Volume"].tail(20).mean() + 1e-9)
    rvol_score = min((rvol / 2.0) * 4.0, 4.0)

    # 4. OBV Slope
    close_diff = df["Close"].diff()
    direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
    obv = (direction * df["Volume"]).cumsum()
    obv_20 = obv.tail(20)
    x = np.arange(len(obv_20))
    slope = np.polyfit(x, obv_20.values, 1)[0]
    obv_score = 5.0 if slope > 0 else 0.0

    total_vol_score = dryup_score + expansion_score + rvol_score + obv_score
    return min(total_vol_score, 20.0), round(rvol, 2), round(dryup_ratio, 2)


# ==============================
# 4. WEIGHTED PATTERN POINTS (30 PTS MAX)
# ==============================
def calculate_pattern_score(df, pivot_high):
    """
    Differentiated weights across pattern geometry:
    - Handle Quality & Rim Proximity : 10 Pts Max
    - Base Maturity (U-Shape)         : 8 Pts Max
    - Pivot Proximity (Strict <=1.5%) : 7 Pts Max
    - Base Depth Calibration (12-35%) : 5 Pts Max
    """
    price = float(df["Close"].iloc[-1])
    low_6m = float(df["Low"].tail(120).min())

    # 1. Base Depth (5 Pts)
    base_depth = (pivot_high - low_6m) / pivot_high * 100.0
    depth_score = 0.0
    if 12.0 <= base_depth <= 35.0:
        depth_score = 5.0
    elif 35.0 < base_depth <= 45.0:
        depth_score = 3.0

    # 2. Handle Quality & Rim Proximity (10 Pts)
    handle = df["Close"].tail(15)
    handle_range = (handle.max() - handle.min()) / handle.min()
    handle_low = handle.min()
    rim_threshold = pivot_high * (1.0 - HANDLE_RIM_PCT)

    handle_score = 0.0
    if handle_range < 0.10 and handle_low >= rim_threshold:
        handle_score = 10.0
    elif handle_range < 0.15 and handle_low >= rim_threshold:
        handle_score = 6.0

    # 3. Base Maturity (U-Shape) (8 Pts)
    cup_body = df.tail(120)
    bottom_zone_ceiling = low_6m + BASE_BOTTOM_ZONE_PCT * (pivot_high - low_6m)
    days_in_bottom = (cup_body["Close"] <= bottom_zone_ceiling).sum()
    
    maturity_score = 0.0
    if days_in_bottom >= 20: maturity_score = 8.0
    elif days_in_bottom >= MIN_DAYS_IN_BASE_BOTTOM: maturity_score = 5.0

    # 4. Pivot Proximity Gatekeeper (7 Pts)
    # Strict Threshold: Must be within 1.5% of pivot or breaking out above it
    pivot_dist_pct = (pivot_high - price) / pivot_high * 100.0
    pivot_score = 0.0
    if price >= pivot_high:
        pivot_score = 7.0  # Active Breakout
    elif pivot_dist_pct <= 1.5:
        pivot_score = 5.0  # Immediate Pivot Threat
    elif pivot_dist_pct <= 3.0:
        pivot_score = 2.0  # Approaching

    total_pattern_score = depth_score + handle_score + maturity_score + pivot_score
    return min(total_pattern_score, 30.0), round(pivot_dist_pct, 2)


# ==============================
# MAIN SCANNER ENGINE
# ==============================
def run(output_dir=None, save=True):
    print("\n🚀 INSTITUTIONAL CUP & HANDLE SCANNER (V3 - MULTI-FACTOR MATRIX)\n")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    })

    symbols = load_symbols_full()
    print(f"📡 Processing {len(symbols)} stocks across multi-factor pipeline...\n")

    print("📈 Fetching Nifty 50 reference data...")
    nifty_s = load_nifty_reference(session)

    stock_cache = {}
    raw_rs_map = {}
    total_symbols = len(symbols)

    # PASS 1: Batched Ingestion & Baseline Filtering
    print("\n[PASS 1] Ingesting Historical OHLCV Data...")
    for i in range(0, total_symbols, BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        try:
            data = yf.download(batch, period=LOOKBACK, interval="1d", group_by="ticker", threads=True, progress=False, auto_adjust=True, session=session)
        except Exception as e:
            continue

        for sym in batch:
            try:
                df = data[sym].dropna() if len(batch) > 1 else data.dropna()
                if df.empty or len(df) < 252:
                    continue

                # Liquidity Check (≥ ₹3 Cr Turnover)
                avg_turnover = (df["Close"].tail(20) * df["Volume"].tail(20)).mean()
                if avg_turnover < MIN_DAILY_TURNOVER:
                    continue

                stock_cache[sym] = df

                # Blended Relative Strength Calculation
                blended_rs = calculate_blended_excess_return(df, nifty_s)
                if blended_rs is not None:
                    raw_rs_map[sym] = blended_rs
            except:
                continue
                
        time.sleep(0.8)

    if not stock_cache:
        print("\n❌ No stocks passed initial liquidity filters.")
        return pd.DataFrame()

    # PASS 2: Deterministic Percentile Ranking
    print(f"\n[PASS 2] Computing Deterministic RS Percentile Ranks ({len(raw_rs_map)} assets)...")
    if raw_rs_map:
        rs_series = pd.Series(raw_rs_map)
        # Using method="average" to ensure deterministic tie-breaking
        rs_percentiles = (rs_series.rank(method="average", pct=True) * 100.0).to_dict()
    else:
        rs_percentiles = {}

    # PASS 3: Quantitative Pattern & Component Scoring
    print("\n[PASS 3] Executing Multi-Factor Pattern & Diagnostic Scoring...")
    results = []

    for sym, df in stock_cache.items():
        try:
            price = float(df["Close"].iloc[-1])
            pivot_high = float(df["High"].tail(252).max())

            # 1. Pattern Score (Max 30)
            score_pattern, pivot_dist_pct = calculate_pattern_score(df, pivot_high)

            # Strict Gatekeeper: Reject candidates floating >3% below pivot
            if pivot_dist_pct > 3.0 and price < pivot_high:
                continue

            # 2. RS Score (Max 25)
            rs_pctile = rs_percentiles.get(sym, 50.0)
            score_rs = round((rs_pctile / 100.0) * 25.0, 1)

            # RS Grade
            if rs_pctile >= 95:    rs_grade = "A+"
            elif rs_pctile >= 90:  rs_grade = "A"
            elif rs_pctile >= 80:  rs_grade = "B"
            elif rs_pctile >= 65:  rs_grade = "C"
            elif rs_pctile >= 50:  rs_grade = "D"
            else:                      rs_grade = "F"

            # 3. Volume Score (Max 20)
            score_volume, rvol, dryup_ratio = calculate_volume_score(df)

            # 4. Trend Score (Max 15)
            score_trend = calculate_trend_score(df)

            # 5. Liquidity Score (Max 10)
            turnover_cr = (df["Close"].tail(20) * df["Volume"].tail(20)).mean() / 1e7
            score_liquidity = min((turnover_cr / 25.0) * 10.0, 10.0)

            # Total Composite Score
            total_score = round(score_pattern + score_rs + score_volume + score_trend + score_liquidity, 1)

            # Quality Tiering with RS Gatekeeper
            if total_score >= 75 and rs_pctile >= 65:
                quality = "STRONG SETUP"
            elif total_score >= 60 and rs_pctile >= 50:
                quality = "WATCHLIST"
            else:
                quality = "BUILDING BASE"

            results.append({
                "Stock": sym.replace(".NS", ""),
                "Price": round(price, 2),
                "Pivot": round(pivot_high, 2),
                "Dist_to_Pivot_%": pivot_dist_pct,
                "Total_Score": total_score,
                "Quality": quality,
                "RS_Grade": rs_grade,
                "RS_Percentile": round(rs_pctile, 1),
                "Score_Pattern": round(score_pattern, 1),
                "Score_RS": score_rs,
                "Score_Volume": round(score_volume, 1),
                "Score_Trend": round(score_trend, 1),
                "Score_Liquidity": round(score_liquidity, 1),
                "RVOL": rvol,
                "DryUp_Ratio": dryup_ratio,
                "Turnover_Cr": round(turnover_cr, 2)
            })
        except:
            continue

    if not results:
        print("\n❌ No setups met strict pivot proximity and pattern criteria.")
        return pd.DataFrame()

    out = pd.DataFrame(results).sort_values("Total_Score", ascending=False).reset_index(drop=True)

    print("\n📊 TOP INSTITUTIONAL CUP & HANDLE SETUPS:\n")
    print(out.head(25).to_string(index=False))

    if save:
        out_path = (
            os.path.join(output_dir, "INSTITUTIONAL_CUP_HANDLE.xlsx")
            if output_dir else "INSTITUTIONAL_CUP_HANDLE.xlsx"
        )
        out.to_excel(out_path, index=False)
        print(f"\n📁 Saved → {out_path}")

    return out


if __name__ == "__main__":
    run()