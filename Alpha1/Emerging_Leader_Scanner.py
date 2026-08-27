# =============================================================================
# 🚀 TRUE EARLY-STAGE FUTURE LEADER DISCOVERY ENGINE v14.1
# Phase Segmentation + Overextension Penalty + Hard Scarcity (Shortlist Integrated)
#
# Changes from v14.0:
#   1. Shortlist minimum size check (Option A fix):
#      If FUNDAMENTAL_SHORTLIST.xlsx exists but contains fewer than 50 tickers,
#      the scanner ignores it and falls back to the full NSE universe from
#      nse_eq.csv. Previously 3 tickers from a small Fundamental.py run would
#      silently constrain the entire scan, producing meaningless results.
#      Threshold: 50 tickers minimum to use the shortlist as the universe.
#
#   2. Output filename changed from Alpha_PhaseSegment_Scan.xlsx to
#      WEEKLY_WATCHLIST.xlsx so Breakout_Trigger_Scanner.py can find it
#      automatically. Also saved to BASE_DIR (absolute path) rather than
#      the working directory, consistent with all other pipeline outputs.
# =============================================================================

print("⚙️ Initializing Quant Engine & Loading Libraries...")

import pandas as pd
import numpy as np
import yfinance as yf
import requests
import os
import sys
import warnings
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

warnings.filterwarnings("ignore")

# =============================================================================
# SETTINGS & PIPELINE CONTROLS
# =============================================================================

BASE_DIR             = r"C:\Users\GS102\OneDrive\Research\Invest"
CSV_PATH             = os.path.join(BASE_DIR, "nse_eq.csv")
FUNDAS_CACHE_PATH    = os.path.join(BASE_DIR, "fundamentals_cache.csv")
SHORTLIST_INPUT_PATH = os.path.join(BASE_DIR, "FUNDAMENTAL_SHORTLIST.xlsx")

# Minimum number of tickers a shortlist must contain to be used as the
# scanning universe. Below this threshold the full NSE universe is used
# instead -- prevents a 3-stock Fundamental.py run from silently capping
# the entire Emerging Leader scan.
MIN_SHORTLIST_SIZE = 50

MAX_WORKERS = 6
TOP_N       = 20
LOOKBACK    = "2y"

MIN_PRICE           = 30
MIN_DAILY_TURNOVER  = 50000000  # 5 Crores INR

yf_session = requests.Session()
yf_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
})


def safe_div(a, b):
    try:
        if isinstance(a, pd.Series) or isinstance(b, pd.Series):
            return a.divide(b).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        if b is None or b == 0 or (isinstance(b, float) and np.isnan(b)):
            return 0.0
        if a is None or (isinstance(a, float) and np.isnan(a)):
            return 0.0
        return float(a / b)
    except:
        return 0.0


def load_symbols():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"❌ File not found: {CSV_PATH}")
    print("📡 Loading NSE EQ symbols from full universe...")
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip().upper() for c in df.columns]
    if "SERIES" in df.columns:
        df = df[df["SERIES"] == "EQ"]

    symbol_industry_map = {}
    if "INDUSTRY" in df.columns:
        for _, row in df.iterrows():
            sym = str(row["SYMBOL"]).strip().upper() + ".NS"
            symbol_industry_map[sym] = str(row["INDUSTRY"]).strip().upper()

    symbols = (
        df["SYMBOL"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )
    clean = [
        s + ".NS" for s in symbols
        if len(s) >= 2 and not any(
            x in s for x in ["/", "\\", " ", "&", "*", "DUMMY"]
        )
    ]
    print(f"✅ Loaded {len(clean)} symbols from nse_eq.csv")
    return clean, symbol_industry_map


def load_fundamentals_cache():
    if os.path.exists(FUNDAS_CACHE_PATH):
        try:
            return pd.read_csv(
                FUNDAS_CACHE_PATH, index_col="Symbol"
            ).to_dict(orient="index")
        except:
            return {}
    return {}


def calculate_atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(period).mean()


def calculate_slope(series, window):
    if len(series) < window:
        return 0.0
    y = np.log(series.tail(window).replace(0, np.nan)).dropna()
    if len(y) < (window // 2) or not np.isfinite(y).all():
        return 0.0
    return float(np.polyfit(np.arange(len(y)), y.values, 1)[0])


def get_fundamentals(symbol, fundas_cache):
    if symbol in fundas_cache:
        data = fundas_cache[symbol]
        shares = data.get("Free Float Shares", 0)
        used_float = True if shares > 0 else False
        if not used_float:
            shares = data.get("Shares Outstanding", 10000000)
        return (
            data.get("Sales Gr", 0.0),
            data.get("Profit Gr", 0.0),
            bool(data.get("Turnaround", False)),
            bool(data.get("Loss Reduction", False)),
            bool(data.get("Earn Accel", False)),
            data.get("Latest NI", 1.0),
            10000000 if not shares or shares == 0 else shares,
            used_float
        )
    try:
        tkr = yf.Ticker(symbol, session=yf_session)
        inc = getattr(tkr, "quarterly_financials", pd.DataFrame())
        if inc.empty and hasattr(tkr, "quarterly_income_stmt"):
            inc = tkr.quarterly_income_stmt
        free_float_shares = (
            tkr.info.get("floatShares", 0) if hasattr(tkr, "info") else 0
        )
        used_float = True
        if not free_float_shares or free_float_shares == 0:
            free_float_shares = (
                tkr.info.get("sharesOutstanding", 10000000)
                if hasattr(tkr, "info") else 10000000
            )
            used_float = False
        if inc.empty or inc.shape[1] < 6:
            return 0.0, 0.0, False, False, False, 1.0, free_float_shares, used_float

        sg, pg = 0.0, 0.0
        turnaround = loss_red = earn_accel = False
        latest_ni = 1.0

        idx_rev = next(
            (c for c in ["Total Revenue", "Revenue"] if c in inc.index), None
        )
        idx_ni = "Net Income" if "Net Income" in inc.index else None

        if idx_rev:
            revs = inc.loc[idx_rev]
            if len(revs) >= 5 and revs.iloc[4] > 0:
                sg = safe_div(revs.iloc[0], revs.iloc[4]) - 1
        if idx_ni:
            nis = inc.loc[idx_ni]
            if len(nis) >= 6:
                latest_ni = nis.iloc[0]
                if nis.iloc[4] < 0 and nis.iloc[0] > 0:
                    turnaround = True
                elif (
                    nis.iloc[4] < 0 and nis.iloc[0] < 0
                    and abs(nis.iloc[0]) < abs(nis.iloc[4]) * 0.7
                ):
                    loss_red = True
                g0 = (
                    safe_div(nis.iloc[0], nis.iloc[4]) - 1
                    if nis.iloc[4] > 0 else 0.0
                )
                g1 = (
                    safe_div(nis.iloc[1], nis.iloc[5]) - 1
                    if nis.iloc[5] > 0 else 0.0
                )
                if g0 > g1 and (g0 - g1 > 0.10) and g0 > 0:
                    earn_accel = True
                if nis.iloc[4] > 0:
                    pg = g0

        return (
            sg, pg, turnaround, loss_red, earn_accel,
            latest_ni, free_float_shares, used_float
        )
    except:
        return 0.0, 0.0, False, False, False, 1.0, 10000000, False


# =============================================================================
# PASS 1: EXTRACT METRICS & ENFORCE STRICT PHASE GATES
# =============================================================================

def extract_metrics(
    symbol, df, nifty_close, nifty_atr_pct, fundas_cache, industry_name
):
    if df is None or df.empty or len(df) < 200:
        return None
    try:
        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"]
        price  = float(close.iloc[-1])

        sma50      = close.rolling(50).mean()
        sma200     = close.rolling(200).mean()
        sma50_today  = float(sma50.iloc[-1])
        sma200_today = float(sma200.iloc[-1])

        avg_20_volume      = float(volume.tail(20).mean())
        is_institutional_pool = (
            (avg_20_volume * price) >= MIN_DAILY_TURNOVER
        )

        high_52w    = float(high.max())
        low_52w     = float(low.min())
        from_high   = safe_div((price - high_52w), high_52w) * 100
        pct_above_low = safe_div((price - low_52w), low_52w) * 100
        closes_below_200_6m = int(
            (close.tail(126) < sma200.tail(126)).sum()
        )

        pivot      = float(high.tail(30).iloc[:-5].max())
        pivot_dist = safe_div((price - pivot), pivot) * 100

        is_extended = (pivot_dist > 5.0) and (from_high > -5.0)
        is_constructing_base = (
            (-35.0 <= from_high <= -8.0) or (abs(pivot_dist) <= 4.0)
        )

        overnight_gaps = safe_div(
            abs(df["open"] - df["close"].shift(1)),
            df["close"].shift(1)
        ) * 100
        extreme_gap_shocks = int(
            (overnight_gaps.tail(20) > 12.0).sum()
        )

        benchmark = nifty_close.reindex(close.index).ffill().bfill()
        rs_line   = safe_div(close, benchmark)
        rolling_peaks = rs_line.cummax()
        rs_max_drawdown = float(
            (
                safe_div((rs_line - rolling_peaks), rolling_peaks) * 100
            ).tail(252).min()
        )

        passed_technical_gate = (
            is_institutional_pool
            and is_constructing_base
            and not is_extended
            and (price >= sma200_today * 0.93)
            and (sma50_today < sma200_today * 1.25)
            and (closes_below_200_6m <= 60)
            and (extreme_gap_shocks <= 1)
            and (rs_max_drawdown >= -30.0)
        )

        if passed_technical_gate:
            (
                sales_growth, profit_growth, turnaround, loss_reduction,
                earn_accel, latest_ni, free_float_shares, used_float
            ) = get_fundamentals(symbol, fundas_cache)
            passed_fundamental_gate = not (
                latest_ni < 0 and not turnaround and not loss_reduction
            )
        else:
            (
                sales_growth, profit_growth, turnaround, loss_reduction,
                earn_accel, latest_ni, free_float_shares, used_float
            ) = 0.0, 0.0, False, False, False, 1.0, 10000000, False
            passed_fundamental_gate = False

        passed_gate = bool(passed_technical_gate and passed_fundamental_gate)

        slope_20 = calculate_slope(rs_line, 20)
        slope_60 = calculate_slope(rs_line, 60)
        rs_acceleration_factor = (
            slope_20 + slope_60
            if (slope_20 > 0 and slope_60 > 0)
            else (slope_20 * 0.5)
        )

        rs_3m  = safe_div(
            safe_div(close.iloc[-1], close.iloc[-63]),
            safe_div(nifty_close.iloc[-1], nifty_close.iloc[-63])
        )
        rs_6m  = safe_div(
            safe_div(close.iloc[-1], close.iloc[-126]),
            safe_div(nifty_close.iloc[-1], nifty_close.iloc[-126])
        )
        rs_12m = safe_div(
            safe_div(close.iloc[-1], close.iloc[-252]),
            safe_div(nifty_close.iloc[-1], nifty_close.iloc[-252])
        )
        composite_rs = (rs_3m * 0.20 + rs_6m * 0.40 + rs_12m * 0.40)

        rs_trend = (
            rs_line.iloc[-1] > rs_line.rolling(20).mean().iloc[-1]
        )

        cross_days = (sma50 > sma200) & (sma50.shift(1) <= sma200.shift(1))
        gc_idx = np.where(cross_days)[0]
        days_since_cross = (
            len(cross_days) - 1 - gc_idx[-1]
            if len(gc_idx) > 0 else 999
        )
        slope200 = (
            safe_div(sma200_today, float(sma200.iloc[-21])) - 1
        ) * 100

        accum_ratio = safe_div(
            volume.where(close > close.shift(1)).tail(20).median(),
            volume.where(close < close.shift(1)).tail(20).median()
        )
        rvol = safe_div(
            float(volume.iloc[-1]),
            float(volume.tail(20).mean())
        )
        breakout_rvol = safe_div(
            float(volume.iloc[-1]),
            float(volume.tail(51).iloc[:-1].mean())
        )

        base_range_pct = safe_div(
            (float(high.max()) - float(low.min())), float(high.max())
        ) * 100
        atr     = calculate_atr(df, 14).ffill().bfill().fillna(0.0)
        atr_pct = safe_div(float(atr.iloc[-1]), price) * 100.0
        vol_contraction_ratio = safe_div(
            float(atr.iloc[-1]), float(atr.tail(40).mean())
        )
        tight_closes = safe_div(
            (close.tail(10).max() - close.tail(10).min()),
            close.tail(10).mean()
        ) * 100

        return {
            "Symbol":                  str(symbol),
            "Price":                   round(price, 2),
            "Industry":                industry_name if industry_name else "UNKNOWN",
            "Composite RS":            composite_rs,
            "RS Acceleration Factor":  rs_acceleration_factor,
            "RS Trend":                rs_trend,
            "Days Since Cross":        days_since_cross,
            "Slope 200":               round(slope200, 2),
            "above_50":                (price >= sma50_today),
            "above_200":               (price >= sma200_today),
            "Accum Ratio":             round(accum_ratio, 2),
            "RVOL":                    round(rvol, 2),
            "Breakout RVOL":           round(breakout_rvol, 2),
            "Base %":                  round(base_range_pct, 1),
            "Vol Contraction Ratio":   round(vol_contraction_ratio, 2),
            "Tight Closes":            round(tight_closes, 2),
            "ATR %":                   round(atr_pct, 2),
            "From High %":             round(from_high, 1),
            "Pivot Dist":              round(pivot_dist, 2),
            "Sales Gr %":              round(sales_growth * 100, 1),
            "Profit Gr %":             round(profit_growth * 100, 1),
            "Turnaround":              turnaround,
            "Loss Reduction":          loss_reduction,
            "Earn Accel":              earn_accel,
            "Used Float":              used_float,
            "passed_gate":             passed_gate,
        }
    except:
        return None


# =============================================================================
# MAIN SCANNER RUN
# =============================================================================

def run():
    print("\n======================================================")
    print("🚀 TRUE EARLY-STAGE DISCOVERY ENGINE v14.1")
    print("Phase Segmentation + Overextension Penalty + Scarcity")
    print("======================================================\n")

    symbol_industry_map = {}

    # ── Universe selection with minimum size guard (Option A) ──────────────
    if os.path.exists(SHORTLIST_INPUT_PATH):
        shortlist = pd.read_excel(SHORTLIST_INPUT_PATH)
        n = len(shortlist)
        if n >= MIN_SHORTLIST_SIZE:
            symbols = [
                s + ".NS" if not str(s).endswith(".NS") else str(s)
                for s in shortlist["ticker"].dropna().tolist()
            ]
            print(
                f"✅ Using Fundamental Shortlist Matrix: "
                f"{len(symbols)} tickers loaded."
            )
        else:
            print(
                f"⚠️  FUNDAMENTAL_SHORTLIST.xlsx found but has only "
                f"{n} tickers (minimum required: {MIN_SHORTLIST_SIZE})."
            )
            print(
                f"   Ignoring shortlist — falling back to full NSE "
                f"universe from nse_eq.csv."
            )
            print(
                f"   Tip: run Fundamental.py with a larger stock list, "
                f"or delete the shortlist file to suppress this warning."
            )
            symbols, symbol_industry_map = load_symbols()
    else:
        print(
            f"ℹ️  No FUNDAMENTAL_SHORTLIST.xlsx found — "
            f"scanning full NSE universe."
        )
        symbols, symbol_industry_map = load_symbols()
    # ── End universe selection ─────────────────────────────────────────────

    fundas_cache = load_fundamentals_cache()

    print("📈 Evaluating NIFTY50 Index Core Baseline Health... ")
    nifty = yf.download(
        "^NSEI", period=LOOKBACK,
        auto_adjust=True, progress=False, session=yf_session
    )
    if nifty.empty:
        print("❌ Could not download NIFTY data.")
        return
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)
    nifty.columns = [str(c).strip().lower() for c in nifty.columns]
    nifty = nifty.dropna()
    nifty.index = pd.to_datetime(nifty.index)
    if nifty.index.tz is not None:
        nifty.index = nifty.index.tz_localize(None)
    nifty_close = nifty["close"]

    nifty_sma50  = nifty_close.rolling(50).mean().iloc[-1]
    nifty_sma200 = nifty_close.rolling(200).mean().iloc[-1]
    print("Base OK ✅")

    print(
        f"\n📡 Batch downloading historical data for "
        f"{len(symbols)} symbols. This may take a few minutes..."
    )
    bulk_data = yf.download(
        symbols, period=LOOKBACK,
        auto_adjust=True, threads=True, progress=False, session=yf_session
    )

    print(f"🔍 Executing phase-segmentation arrays...")
    raw_results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for symbol in symbols:
            try:
                df_sym = pd.DataFrame({
                    "open":   bulk_data["Open"][symbol],
                    "high":   bulk_data["High"][symbol],
                    "low":    bulk_data["Low"][symbol],
                    "close":  bulk_data["Close"][symbol],
                    "volume": bulk_data["Volume"][symbol],
                }).dropna()
                df_sym.index = pd.to_datetime(df_sym.index)
                if df_sym.index.tz is not None:
                    df_sym.index = df_sym.index.tz_localize(None)
                if len(df_sym) >= 200:
                    futures[executor.submit(
                        extract_metrics, symbol, df_sym, nifty_close,
                        0.0, fundas_cache,
                        symbol_industry_map.get(symbol, "UNKNOWN")
                    )] = symbol
            except:
                continue

        total = len(futures)
        for i, future in enumerate(as_completed(futures), start=1):
            res = future.result()
            if res:
                raw_results.append(res)
            if i % 100 == 0:
                print(
                    f"⏳ {i}/{total} processed | "
                    f"{len([x for x in raw_results if x.get('passed_gate')])} "
                    f"bases detected..."
                )

    full_universe_df = pd.DataFrame(raw_results)
    if full_universe_df.empty:
        print("\n⚠️ No data returned from scan.")
        return
    full_universe_df = (
        full_universe_df
        .replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["Composite RS"])
    )

    df = full_universe_df[
        full_universe_df["passed_gate"] == True
    ].copy()
    if df.empty:
        print("\n⚠️ No setups survived the phase segmentation gates.")
        return

    breadth_50  = (
        len(df[df["above_50"]  == True]) / len(df)
    ) * 100
    breadth_200 = (
        len(df[df["above_200"] == True]) / len(df)
    ) * 100
    regime_healthy = (breadth_50 > 50.0 and breadth_200 > 60.0)

    # Two-axis rank scoring
    df["RS Global Rank"]       = df["Composite RS"].rank(pct=True)
    df["RS Accel Rank"]        = df["RS Acceleration Factor"].rank(pct=True)
    df["Tightness Rank"]       = 1.0 - df["Tight Closes"].rank(pct=True)
    df["Vol Contraction Rank"] = 1.0 - df["Vol Contraction Ratio"].rank(pct=True)
    funda_max_growth = df[["Sales Gr %", "Profit Gr %"]].max(axis=1).clip(lower=0)
    df["Fundamental Rank"]     = funda_max_growth.rank(pct=True)
    df["Breakout RVOL Rank"]   = df["Breakout RVOL"].rank(pct=True)

    df["Emergence Score"] = (
        (0.40 * df["RS Accel Rank"])
        + (0.30 * df["Tightness Rank"])
        + (0.30 * df["Vol Contraction Rank"])
    )
    df["Quality Momentum Score"] = (
        (0.40 * df["Breakout RVOL Rank"])
        + (0.30 * df["RS Global Rank"])
        + (0.30 * df["Fundamental Rank"])
    )
    df["Master Score"] = (
        0.60 * df["Emergence Score"]
    ) + (0.40 * df["Quality Momentum Score"])
    df = df.sort_values(
        by="Master Score", ascending=False
    ).reset_index(drop=True)

    if regime_healthy:
        regime_label = "RISK-ON 🔥"
        max_leaders, max_accel, max_accum = 10, 20, 30
    else:
        regime_label = "DEFENSIVE ❌"
        max_leaders, max_accel, max_accum = 3, 8, 15

    conditions = [
        df.index < max_leaders,
        (df.index >= max_leaders) & (df.index < max_leaders + max_accel),
        (df.index >= max_leaders + max_accel) & (
            df.index < max_leaders + max_accel + max_accum
        )
    ]
    choices = ["🚀 FUTURE LEADER", "⭐ EARLY ACCEL", "🟢 QUIET ACCUM"]
    df["Signal"] = np.select(
        conditions, choices, default="🔵 DEVELOPING BASE"
    )

    df["RS Display"]          = (
        df["RS Global Rank"] * 100
    ).round(1).astype(str) + "%"
    df["Emergence Rank"]      = (df["Emergence Score"] * 100).round(1)
    df["From High % Display"] = df["From High %"].round(2).astype(str) + "%"
    df["Base % Display"]      = df["Base %"].round(2).astype(str) + "%"
    df["Pivot Dist Display"]  = df["Pivot Dist"].round(2).astype(str) + "%"
    df["Turnaround"]          = np.where(
        df["Turnaround"], "🏆 YES",
        np.where(df["Loss Reduction"], "📉 REDUCING", "❌")
    )
    df["RS Trend"]    = np.where(df["RS Trend"], "✅", "❌")
    df["Used Float"]  = np.where(df["Used Float"], "🔒 FF", "⚠️ OUT")
    df["Golden Cross"] = np.where(
        df["Days Since Cross"] <= 40, "🔥 FRESH", "✅ YES"
    )

    final_cols = [
        "Symbol", "Price", "Signal", "Emergence Rank",
        "RS Display", "RS Trend", "Golden Cross",
        "Accum Ratio", "Breakout RVOL", "Tight Closes",
        "ATR %", "Base % Display", "Pivot Dist Display",
        "From High % Display", "Sales Gr %", "Profit Gr %",
        "Turnaround", "Used Float",
    ]
    out = df[final_cols]

    emerging_leaders = out[out["Signal"] == "🚀 FUTURE LEADER"]
    early_stage      = out[out["Signal"] == "⭐ EARLY ACCEL"]
    watchlist        = out[out["Signal"] == "🟢 QUIET ACCUM"]
    developing       = out[out["Signal"] == "🔵 DEVELOPING BASE"]

    print("\n======================================================")
    print("🌍 PHASE SEGMENTATION & MARKET BREADTH STATUS")
    print("======================================================")
    print(f"📦 Surviving Bases Detected  : {len(df)}")
    print(f"📊 50-DMA Market Breadth     : {round(breadth_50, 2)}%")
    print(f"📊 200-DMA Market Breadth    : {round(breadth_200, 2)}%")
    print(f"💼 Operating Macro Regime    : {regime_label}")

    print("\n======================================================")
    print("📊 STRICT SCARCITY ALLOCATION (REGIME GATED)")
    print("======================================================")
    print(f"🚀 Future Leaders      : {len(emerging_leaders)} (Max {max_leaders})")
    print(f"⭐ Early Acceleration  : {len(early_stage)} (Max {max_accel})")
    print(f"🟢 Quiet Accumulation  : {len(watchlist)} (Max {max_accum})")
    print(f"🔵 Developing Bases    : {len(developing)}")

    if not emerging_leaders.empty:
        print("\n🚀 FUTURE LEADERS (Maximum Emergence Phase):\n")
        print(emerging_leaders.head(TOP_N).to_string(index=False))

    if not out.empty:
        # Output to WEEKLY_WATCHLIST.xlsx in BASE_DIR so that
        # Breakout_Trigger_Scanner.py can locate it automatically.
        # Previously saved as Alpha_PhaseSegment_Scan.xlsx in the
        # working directory — renamed and moved for pipeline consistency.
        output_path = os.path.join(BASE_DIR, "WEEKLY_WATCHLIST.xlsx")
        with pd.ExcelWriter(output_path) as writer:
            out.to_excel(writer, sheet_name="All Setups", index=False)
            if not emerging_leaders.empty:
                emerging_leaders.to_excel(
                    writer, sheet_name="Future Leaders", index=False
                )
            if not early_stage.empty:
                early_stage.to_excel(
                    writer, sheet_name="Early Accel", index=False
                )
            if not watchlist.empty:
                watchlist.to_excel(
                    writer, sheet_name="Quiet Accum", index=False
                )
        print(
            f"\n📁 Production Alpha Leaderboard saved → {output_path}"
        )
        print(
            f"   (Breakout_Trigger_Scanner.py will read this file "
            f"automatically as Source 5)"
        )


if __name__ == "__main__":
    run()