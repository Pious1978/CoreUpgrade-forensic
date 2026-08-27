# ============================================================
# ADVANCED CONSOLIDATION SCANNER v7.3
# Institutional Breakout + Continuous Setup Score Engine
#
# Changes from v7.2:
#   - Range% tier added to output so Master Terminal has
#     granular data instead of a binary pass/fail
#   - Scoring: range_pct_20 bands widened to reduce false
#     eliminations of genuinely good setups with 6-10% range
#   - RS scoring added as a 4th factor (max 20 pts) so RS
#     leaders are ranked higher even before DB percentile
#     is available -- this partially compensates for stale
#     DB scores during gaps between daily runs
#   - Breakout proximity bonus added (max 10 pts) -- a stock
#     0.5% from pivot scores higher than one 8% away
#   - Output now includes Range_Tier column so Decision_Engine
#     can apply graduated tier logic instead of hard 6% cutoff
#   - Total score rescaled: factors sum to 100 max
#     (40 compression + 20 volume + 20 RS + 10 proximity + 10 trend)
#   - Saves both full results AND a Tier_Ready subset
#     (score >= 70, range <= 10%, breakout <= 5%) for faster
#     Master Terminal processing
# ============================================================

import pandas as pd
import yfinance as yf
import numpy as np
import time
import warnings
import os
import logging

# Silence unnecessary warnings and internal yfinance logger noise
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# ============================================================
# SETTINGS
# ============================================================
CSV_FILE = "nse_eq.csv"
LOOKBACK = "1y"

MIN_PRICE = 50
MIN_VOLUME = 100000
MIN_TRADED_VALUE = 10_00_00_000   # 10 Crore

MAX_SCAN = 2357
BASE_RANGE_MAX = 25
ATR_THRESHOLD = 0.12
COIL_MAX_LEAKAGE = 0.15

MIN_SCORE = 40

# ============================================================
# LOAD SYMBOLS
# ============================================================
def load_symbols():
    print("\n📡 Loading NSE symbols...")
    try:
        if not os.path.exists(CSV_FILE):
            raise FileNotFoundError(f"Universe CSV file not found at {CSV_FILE}")

        df = pd.read_csv(CSV_FILE)
        cols = [c.upper().strip() for c in df.columns]

        if "SYMBOL" not in cols:
            raise Exception("SYMBOL column missing from CSV layout")

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
            if "DUMMY" in s or "TEST" in s:
                continue
            if not s.endswith(".NS"):
                s += ".NS"
            clean.append(s)

        clean = sorted(list(set(clean)))

        # Explicitly filter only genuinely dead/permanently suspended tickers
        KNOWN_DEAD = {"FLFL", "CPL"}
        clean = [s for s in clean if s.replace(".NS", "") not in KNOWN_DEAD]

        print(f"✅ Loaded {len(clean)} structured symbols")
        return clean[:MAX_SCAN]

    except Exception as e:
        print(f"❌ Error loading symbols: {e}")
        return []

# ============================================================
# ATR CALCULATION
# ============================================================
def calculate_atr(df, period=14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

# ============================================================
# RELATIVE STRENGTH VS NIFTY
# ============================================================
def calculate_rs(stock_close, nifty_close):
    try:
        if len(stock_close) < 60 or len(nifty_close) < 60:
            return np.nan
        stock_return = stock_close.iloc[-1] / stock_close.iloc[-60]
        nifty_return = nifty_close.iloc[-1] / nifty_close.iloc[-60]
        rs = stock_return / nifty_return
        return round(float(rs), 2)
    except:
        return np.nan

# ============================================================
# RANGE TIER CLASSIFICATION
# Used by Master Terminal Decision Engine for graduated
# tier assignment instead of a hard 6% binary cutoff
# ============================================================
def range_tier(range_pct):
    if range_pct <= 6.0:
        return "COILED"          # Tier 1 ready — tightest compression
    elif range_pct <= 10.0:
        return "TIGHTENING"      # Tier 1 watchable — good but not coiled
    elif range_pct <= 15.0:
        return "FORMING"         # Tier 2 — base still building
    else:
        return "WIDE"            # Tier 2 — needs significant tightening

# ============================================================
# COMMENTARY ENGINE
# ============================================================
def rs_comment(rs):
    if pd.isna(rs): return "N/A"
    if rs >= 1.30: return "🚀 Massive Outperformance"
    elif rs >= 1.15: return "🔥 Strong Leader"
    elif rs >= 1.00: return "✅ Beating NIFTY"
    elif rs >= 0.90: return "⚠️ Market Performer"
    return "❌ Weak vs NIFTY"

def atr_comment(atr_pct):
    if atr_pct <= 2: return "🔥 Extreme Compression"
    elif atr_pct <= 3: return "✅ Tight Volatility"
    elif atr_pct <= 4: return "⚠️ Moderate Compression"
    return "❌ Loose Structure"

def tight_close_comment(tight):
    if tight <= 1: return "🔥 Institutional Tightness"
    elif tight <= 2: return "✅ Tight Closes"
    elif tight <= 3: return "⚠️ Average Tightness"
    return "❌ Loose Closes"

def volume_comment(recent_vol, old_vol):
    if old_vol == 0: return "N/A"
    ratio = recent_vol / old_vol
    if ratio <= 0.60: return "🔥 Major Volume Dry-Up"
    elif ratio <= 0.80: return "✅ Healthy Dry-Up"
    elif ratio <= 1.0: return "⚠️ Mild Dry-Up"
    return "❌ Expansion Volume"

def breakout_comment(distance):
    if distance <= 1: return "🔥 Near Breakout"
    elif distance <= 3: return "✅ Setup Approaching Pivot"
    elif distance <= 5: return "⚠️ Slightly Extended"
    return "❌ Needs More Tightening"

def rvol_comment(rvol):
    if rvol >= 2: return "🚀 Massive Relative Volume"
    elif rvol >= 1.5: return "🔥 Strong Volume Interest"
    elif rvol >= 1: return "✅ Healthy Participation"
    return "⚠️ Below Average Activity"

def breakout_volume_comment(breakout_volume):
    if breakout_volume: return "🚀 Breakout Volume Confirmed"
    return "⚠️ Awaiting Expansion Volume"

def score_comment(score):
    if score >= 85: return "🚀 Institutional Monster"
    elif score >= 70: return "🔥 High Probability Breakout"
    elif score >= 55: return "🔵 Strong Setup"
    elif score >= 40: return "🟡 Watchlist Candidate"
    return "❌ Weak Setup"

# ============================================================
# CORE ANALYSIS ENGINE
# Scoring breakdown (max 100):
#   Factor 1 — Volatility Compression   : 40 pts
#   Factor 2 — Volume Dry-Up            : 20 pts
#   Factor 3 — RS vs Nifty              : 20 pts
#   Factor 4 — Breakout Proximity       : 10 pts
#   Factor 5 — Trend Alignment          : 10 pts
# ============================================================
def analyze_stock(df, nifty_close):
    try:
        if len(df) < 120:
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        current_price = float(close.iloc[-1])

        # ------------------------------------------------
        # LIQUIDITY & PRICE FILTERS
        # ------------------------------------------------
        if current_price < MIN_PRICE:
            return None

        avg_volume = float(volume.tail(20).mean())
        if avg_volume < MIN_VOLUME:
            return None

        avg_traded_value = (close.tail(20) * volume.tail(20)).mean()
        if avg_traded_value < MIN_TRADED_VALUE:
            return None

        # ------------------------------------------------
        # TREND INDICATORS
        # ------------------------------------------------
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        if pd.isna(sma20) or pd.isna(sma50):
            return None

        if current_price > sma20 > sma50:   trend = "UP"
        elif current_price < sma20 < sma50: trend = "DOWN"
        else:                               trend = "SIDEWAYS"

        # ------------------------------------------------
        # VOLATILITY, PIVOT & RANGE METRICS
        # ------------------------------------------------
        high_30 = float(high.tail(30).max())
        low_30  = float(low.tail(30).min())
        base_range = ((high_30 - low_30) / low_30) * 100

        pivot = high_30
        breakout_distance = ((pivot - current_price) / current_price) * 100

        atr     = calculate_atr(df)
        atr_pct = (atr.iloc[-1] / current_price) * 100

        recent_vol   = volume.tail(10).mean()
        old_vol      = volume.tail(40).head(20).mean()
        vol_contract = recent_vol < old_vol

        avg_vol_20      = volume.tail(20).mean()
        vol_ratio       = volume.iloc[-1] / avg_vol_20 if avg_vol_20 > 0 else 1.0
        breakout_volume = volume.iloc[-1] > (avg_vol_20 * 1.5)

        recent_high  = high.tail(15).max()
        recent_low   = low.tail(15).min()
        coil_leakage = (recent_high - recent_low) / recent_low
        coil         = coil_leakage <= COIL_MAX_LEAKAGE

        tight_closes = (close.tail(10).std() / current_price) * 100
        rs           = calculate_rs(close, nifty_close)

        high_20_c    = high.rolling(20).max().iloc[-1]
        low_20_c     = low.rolling(20).min().iloc[-1]
        range_pct_20 = ((high_20_c - low_20_c) / low_20_c) * 100

        r_tier = range_tier(range_pct_20)

        # ============================================================
        # SCORING — max 100 pts across 5 factors
        # ============================================================
        score = 0.0

        # FACTOR 1: Volatility Compression (max 40 pts)
        if range_pct_20 <= 4.0:   score += 40   # Extremely tight
        elif range_pct_20 <= 6.0: score += 35   # Coiled
        elif range_pct_20 <= 8.0: score += 25   # Tightening well
        elif range_pct_20 <= 10.0: score += 15  # Forming
        elif range_pct_20 <= 14.0: score += 5   # Wide but not disqualified

        # FACTOR 2: Volume Dry-Up (max 20 pts)
        if vol_ratio <= 0.5:   score += 20
        elif vol_ratio <= 0.8: score += 14
        elif vol_ratio <= 1.1: score += 7

        # FACTOR 3: RS vs Nifty (max 20 pts)
        if not pd.isna(rs):
            if rs >= 1.30:   score += 20   # Massive outperformance
            elif rs >= 1.15: score += 16   # Strong leader
            elif rs >= 1.00: score += 10   # Beating Nifty
            elif rs >= 0.90: score += 4    # Market performer

        # FACTOR 4: Breakout Proximity (max 10 pts)
        if breakout_distance <= 1.0:   score += 10
        elif breakout_distance <= 2.0: score += 8
        elif breakout_distance <= 3.0: score += 6
        elif breakout_distance <= 5.0: score += 3

        # FACTOR 5: Trend Alignment (max 10 pts)
        if current_price > sma50:
            distance_from_sma50 = (current_price - sma50) / sma50
            if distance_from_sma50 <= 0.05: score += 10  # Hugging 50 SMA
            elif distance_from_sma50 <= 0.15: score += 7
            else: score += 4

        # ------------------------------------------------
        # OUTPUT
        # ------------------------------------------------
        if score >= MIN_SCORE:
            signal = "🟡 WATCH"
            if score >= 55: signal = "🔵 BUY"
            if score >= 70: signal = "🔥 EXPLOSIVE"
            if score >= 85: signal = "🚀 MONSTER"

            return {
                "Price":            round(current_price, 2),
                "Pivot":            round(pivot, 2),
                "Breakout %":       round(breakout_distance, 2),
                "Breakout Note":    breakout_comment(breakout_distance),
                "Trend":            trend,
                "Range%":           round(base_range, 2),
                "Range_20d%":       round(range_pct_20, 2),
                "Range_Tier":       r_tier,
                "ATR%":             round(float(atr_pct), 2),
                "ATR Note":         atr_comment(atr_pct),
                "RS":               rs,
                "RS Note":          rs_comment(rs),
                "RVOL":             round(float(vol_ratio), 2),
                "RVOL Note":        rvol_comment(vol_ratio),
                "Breakout Volume":  "YES" if breakout_volume else "NO",
                "Volume Expansion": breakout_volume_comment(breakout_volume),
                "Vol Dryup":        "YES" if vol_contract else "NO",
                "Volume Note":      volume_comment(recent_vol, old_vol),
                "Coil":             "YES" if coil else "NO",
                "Tight Closes":     round(float(tight_closes), 2),
                "Tightness":        tight_close_comment(tight_closes),
                "Score":            int(score),
                "Action":           score_comment(score),
                "Signal":           signal,
            }
        return None

    except Exception as e:
        print(f"[-] Evaluation error skipped: {e}")
        return None

# ============================================================
# MAIN EXECUTION ROUTINE
# ============================================================
def run():
    print("\n🚀 ADVANCED CONSOLIDATION SCANNER v7.3\n")
    symbols = load_symbols()
    if not symbols:
        return

    print("\n📥 Establishing Index Benchmarks (NIFTY)...")
    nifty = yf.download(
        "^NSEI",
        period=LOOKBACK,
        auto_adjust=True,
        progress=False
    )

    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)

    nifty = nifty.dropna()
    nifty_close = nifty["Close"]

    print(f"\n📡 Running multi-horizon scoring matrix over {len(symbols)} targets...\n")
    results = []

    for i, symbol in enumerate(symbols):
        retries = 2
        for attempt in range(retries):
            try:
                df = yf.download(
                    symbol,
                    period=LOOKBACK,
                    interval="1d",
                    auto_adjust=True,
                    progress=False,
                    threads=False
                )

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.dropna()

                # Handle transient rate-limit blank responses
                if df.empty:
                    if attempt < retries - 1:
                        time.sleep(0.5)
                        continue
                    else:
                        break

                data = analyze_stock(df, nifty_close)
                if data:
                    results.append({"Ticker": symbol, **data})
                break

            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                else:
                    break

        if i % 100 == 0 and i > 0:
            print(f"🔄 Completed evaluation metrics for {i} stocks...")

        # Pace downloads to avoid triggering Yahoo rate limits
        time.sleep(0.08)

    if not results:
        print("\n⚠️ No structural setups matched your core scanning parameters.")
        return

    out = pd.DataFrame(results)
    out = out.sort_values(by=["Score", "RS", "RVOL"], ascending=False).reset_index(drop=True)

    # ── Summary by tier ──────────────────────────────────────
    coiled     = out[out["Range_Tier"] == "COILED"]
    tightening = out[out["Range_Tier"] == "TIGHTENING"]
    forming    = out[out["Range_Tier"] == "FORMING"]
    wide       = out[out["Range_Tier"] == "WIDE"]

    print("\n======================================================")
    print("📊 TOP 0-100 INT-GRADE BREAKOUT SETUPS  (v7.3)")
    print("======================================================\n")
    print(out.head(50).to_string(index=False))

    print("\n📊 RANGE TIER SUMMARY")
    print("======================================================")
    print(f"  🔥 COILED     (≤6%  range, Tier 1 ready)  : {len(coiled)}")
    print(f"  ✅ TIGHTENING (6-10% range, Tier 1 watch)  : {len(tightening)}")
    print(f"  🟡 FORMING    (10-15% range, Tier 2)       : {len(forming)}")
    print(f"  ⚠️  WIDE       (>15% range, Tier 2)        : {len(wide)}")
    print(f"  📦 TOTAL      setups isolated              : {len(out)}")

    # ── Save full report ─────────────────────────────────────
    output_file = "Institutional_Breakout_Report.xlsx"
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        out.to_excel(writer, sheet_name="All Setups", index=False)
        coiled.to_excel(writer, sheet_name="COILED (Tier1 Ready)", index=False)
        tightening.to_excel(writer, sheet_name="TIGHTENING (Tier1 Watch)", index=False)
        forming.to_excel(writer, sheet_name="FORMING (Tier2)", index=False)

    print(f"\n📁 Report saved → {output_file}")
    print(f"   Sheets: All Setups | COILED | TIGHTENING | FORMING")
    print(f"✅ Total highly actionable setups isolated: {len(out)}")

if __name__ == "__main__":
    run()