# ============================================================================
# HYBRID INSTITUTIONAL ALPHA SCANNER v24.0 (SOVEREIGN ENGINE)
# Time-Aligned Z-Scores & Decoupled Momentum Taxonomy
# Reconciled: Dynamic Pivot Core Formatting Engine
# ============================================================================

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION SETTINGS
# ============================================================================
CSV_FILE = "NSE_EQ.csv"
LOOKBACK = "2y" 
MAX_SCAN = 2500
BENCHMARK = "^NSEI"

ENABLE_FUNDAMENTALS = False 

# ============================================================================
# GLOBAL STATES & CACHES
# ============================================================================
DATA_CACHE = {}
UNIVERSE_TURNOVER = {}
LIQUIDITY_RATINGS = {}

RS_RATINGS = {}
RS_MOMENTUM_RANK = {}
IND_METRICS = {}

MARKET_BREADTH = {"composite": 0, "regime": "BULLISH", "nifty_20ema_bullish": False, "liq_gate": 30.0}
SYMBOL_INDUSTRY_MAP = {}
BENCHMARK_CLOSE = None

# ============================================================================
# TIME-ALIGNED WEIGHTED SCORE HELPER ENGINE
# ============================================================================
def calculate_weighted_score(series, target_idx):
    """
    Computes the standard O'Neil 40/20/20/20 weighted score relative to a 
    specific target index to prevent historical lookback alignment drift.
    """
    p_target = float(series.iloc[target_idx])
    r3 = (p_target / series.iloc[target_idx - 63]) - 1
    r6 = (p_target / series.iloc[target_idx - 126]) - 1
    r9 = (p_target / series.iloc[target_idx - 189]) - 1
    r12 = (p_target / series.iloc[target_idx - 252]) - 1
    return (0.40 * r3) + (0.20 * r6) + (0.20 * r9) + (0.20 * r12)

# ============================================================================
# DATA INGESTION
# ============================================================================
def load_symbols():
    print("\n📡 Loading NSE Universe...")
    if not os.path.exists(CSV_FILE):
        print(f"[-] Execution Failure: Universe mapping database missing at target path: {CSV_FILE}")
        return []
    try:
        df = pd.read_csv(CSV_FILE)
        cols = [c.upper().strip() for c in df.columns]
        if "SYMBOL" not in cols: return []
        sym_col = df.columns[cols.index("SYMBOL")]
        ind_col = df.columns[cols.index("INDUSTRY")] if "INDUSTRY" in cols else None

        symbols_dict = {}
        for _, row in df.iterrows():
            sym = str(row[sym_col]).upper().strip()
            if len(sym) < 2 or any(x in sym for x in ["/", "\\", " ", "&", "*"]): continue
            if not sym.endswith(".NS"): sym += ".NS"
            ind = str(row[ind_col]).upper().strip() if ind_col else "OTHER"
            symbols_dict[sym] = ind if ind != "NAN" else "OTHER"

        clean = sorted(list(symbols_dict.keys()))[:MAX_SCAN]
        global SYMBOL_INDUSTRY_MAP
        SYMBOL_INDUSTRY_MAP = {s: symbols_dict[s] for s in clean}
        return clean
    except Exception as e:
        print(f"[-] Error parsing core symbol table: {e}")
        return []

def fetch_data(symbol):
    try:
        df = yf.download(symbol, period=LOOKBACK, interval="1d", auto_adjust=True, progress=False, threads=False)
        if df is not None and not df.empty:
            df = df.dropna()
            if len(df) >= 350: 
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                return symbol, df
    except: pass
    return symbol, None

def build_cache(symbols):
    print(f"\n⚡ Building Global Cache ({len(symbols)} equities)...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        for sym, df in executor.map(fetch_data, symbols):
            if df is not None: DATA_CACHE[sym] = df

# ============================================================================
# PRE-COMPUTE: PERCENTILES, BREADTH & ALIGNED MATRICES
# ============================================================================
def precompute_metrics():
    print("\n📊 Pre-computing Metric Arrays & Time-Aligned Matrices...")
    global RS_RATINGS, RS_MOMENTUM_RANK, LIQUIDITY_RATINGS, BENCHMARK_CLOSE
    
    a20, a50, a200, nh, nl = 0, 0, 0, 0, 0
    total = len(DATA_CACHE)
    industry_stocks = {}

    bench_df = yf.download(BENCHMARK, period=LOOKBACK, interval="1d", auto_adjust=True, progress=False, threads=False)
    if bench_df is not None and len(bench_df.dropna()) >= 350:
        if isinstance(bench_df.columns, pd.MultiIndex): bench_df.columns = bench_df.columns.get_level_values(0)
        BENCHMARK_CLOSE = bench_df["Close"].squeeze().dropna()
        MARKET_BREADTH["nifty_20ema_bullish"] = bool(BENCHMARK_CLOSE.iloc[-1] > BENCHMARK_CLOSE.ewm(span=20).mean().iloc[-1])
        
        bench_w_today = calculate_weighted_score(BENCHMARK_CLOSE, -1)
        bench_w_past = calculate_weighted_score(BENCHMARK_CLOSE, -22)
    else:
        bench_w_today, bench_w_past = 0, 0

    for sym, df in DATA_CACHE.items():
        c, v = df["Close"], df["Volume"]
        price = float(c.iloc[-1])
        
        turnover = float(v.iloc[-21:-1].mean() * price) if len(v) > 20 else 0
        UNIVERSE_TURNOVER[sym] = turnover

        if price > c.ewm(span=20).mean().iloc[-1]: a20 += 1
        if price > c.ewm(span=50).mean().iloc[-1]: a50 += 1
        if price > c.rolling(200).mean().iloc[-1]: a200 += 1

    if UNIVERSE_TURNOVER:
        LIQUIDITY_RATINGS = (pd.Series(UNIVERSE_TURNOVER).rank(pct=True) * 100).to_dict()

    if total > 0:
        b20, b50, b200 = (a20/total)*100, (a50/total)*100, (a200/total)*100
        MARKET_BREADTH["composite"] = (0.30 * b20) + (0.30 * b50) + (0.40 * b200)
        
        if MARKET_BREADTH["composite"] < 35.0: 
            MARKET_BREADTH["regime"] = "SEVERE_WEAKNESS"; MARKET_BREADTH["liq_gate"] = 70.0 
        elif MARKET_BREADTH["composite"] < 50.0: 
            MARKET_BREADTH["regime"] = "DEFENSIVE"; MARKET_BREADTH["liq_gate"] = 50.0
        else: 
            MARKET_BREADTH["regime"] = "BULLISH"; MARKET_BREADTH["liq_gate"] = 30.0

    raw_alpha_today = {}
    raw_alpha_past = {}
    for sym, df in DATA_CACHE.items():
        if LIQUIDITY_RATINGS.get(sym, 0) < MARKET_BREADTH["liq_gate"]: continue 
        
        c = df["Close"]
        raw_alpha_today[sym] = calculate_weighted_score(c, -1) - bench_w_today
        raw_alpha_past[sym] = calculate_weighted_score(c, -22) - bench_w_past

        ind = SYMBOL_INDUSTRY_MAP.get(sym, "OTHER")
        if ind != "OTHER": industry_stocks.setdefault(ind, []).append(sym)

    if raw_alpha_today:
        RS_RATINGS = (pd.Series(raw_alpha_today).rank(pct=True) * 100).to_dict()
        
        mu_t, std_t = np.mean(list(raw_alpha_today.values())), np.std(list(raw_alpha_today.values()), ddof=1) + 1e-6
        mu_p, std_p = np.mean(list(raw_alpha_past.values())), np.std(list(raw_alpha_past.values()), ddof=1) + 1e-6
        
        z_deltas = {}
        for sym in raw_alpha_today:
            z_t = (raw_alpha_today[sym] - mu_t) / std_t
            z_p = (raw_alpha_past[sym] - mu_p) / std_p
            z_deltas[sym] = z_t - z_p
            
        RS_MOMENTUM_RANK = (pd.Series(z_deltas).rank(pct=True) * 100).to_dict()

    raw_ind_scores = {}
    for ind, stocks in industry_stocks.items():
        valid_stocks = [s for s in stocks if s in RS_RATINGS and s in UNIVERSE_TURNOVER]
        if len(valid_stocks) < 3: raw_ind_scores[ind] = 50.0; continue
            
        total_log_liq = sum(np.log1p(UNIVERSE_TURNOVER[s]) for s in valid_stocks)
        if total_log_liq > 0:
            raw_ind_scores[ind] = sum(RS_RATINGS[s] * (np.log1p(UNIVERSE_TURNOVER[s]) / total_log_liq) for s in valid_stocks)
        else:
            raw_ind_scores[ind] = 50.0
        
    if raw_ind_scores:
        ind_rank_series = pd.Series(raw_ind_scores).rank(ascending=False, method="dense")
        for ind, score in raw_ind_scores.items():
            IND_METRICS[ind] = {"rs_rating": score, "industry_rank": int(ind_rank_series[ind])}

# ============================================================================
# MASTER SCORING ENGINE
# ============================================================================
def analyze_stock(symbol):
    try:
        df = DATA_CACHE[symbol]
        c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
        if len(c) < 300: return None
        price = float(c.iloc[-1])
        
        # 1. GATEKEEPERS
        liq_pct = LIQUIDITY_RATINGS.get(symbol, 0)
        if liq_pct < MARKET_BREADTH["liq_gate"]: return None
        
        rs_rating = round(RS_RATINGS.get(symbol, 0), 1)
        rs_mom_rank = round(RS_MOMENTUM_RANK.get(symbol, 0), 1)
        if rs_rating < 75.0 and rs_mom_rank < 90.0: return None 

        # 2. FAILURE RISK MODES
        is_dist = (c.pct_change().fillna(0) < -0.002) & (v > v.shift(1).fillna(0))
        dist_days_25 = int(is_dist.tail(25).sum())
        if dist_days_25 >= 6: return None

        # 3. WEINSTEIN STAGE MODEL
        s30, s50, s150, s200 = c.rolling(30).mean().iloc[-1], c.rolling(50).mean().iloc[-1], c.rolling(150).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
        s150_20d = c.rolling(150).mean().shift(20).iloc[-1]
        s200_20d = c.rolling(200).mean().shift(20).iloc[-1]
        
        stage = "STAGE_1"
        if price > s30 > s150 > s200 and s150 > s150_20d and s200 > s200_20d: stage = "STAGE_2"
        elif price < s30 and price > s150: stage = "STAGE_3"
        elif price < s150 and s150 < s200: stage = "STAGE_4"

        if stage not in ["STAGE_1", "STAGE_2"]: return None

        # 4. SURFING PERSISTENCE
        ema_fast = c.ewm(span=20).mean()
        trend_consistency = float((c > ema_fast).tail(30).mean())
        if trend_consistency < 0.60: return None

        # 5. TECHNICAL ANCHORS
        high_52w = float(h.shift(1).rolling(252).max().iloc[-1])
        pivot_45d = float(h.shift(1).rolling(45).max().iloc[-1])
        pivot_20d = float(h.shift(1).rolling(20).max().iloc[-1])

        # 6. VOLATILITY COIL METER
        tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
        atr10, atr40 = tr.rolling(10).mean().iloc[-1], tr.rolling(40).mean().iloc[-1]
        atr_ratio = float(atr10 / atr40) if atr40 > 0 else 1.0
        
        # Calculate dynamic ATR Percentage footprint for downstream sizing engines
        atr_14d_pct = (tr.rolling(14).mean().iloc[-1] / price) * 100.0

        # 7. BREAKOUT INTEGRITY
        vol_50d_avg = float(v.rolling(50).mean().shift(1).iloc[-1])
        rvol_50 = float(v.iloc[-1] / vol_50d_avg) if vol_50d_avg > 0 else 0
        range_today = float(h.iloc[-1] - l.iloc[-1])
        avg_range_20 = float((h - l).rolling(20).mean().shift(1).iloc[-1])
        close_pos = float((price - l.iloc[-1]) / (range_today + 1e-5))

        is_breaking = bool((price > pivot_45d) and (rvol_50 >= 1.5) and (range_today > (avg_range_20 * 1.2)) and (close_pos >= 0.50))
        vol_expansion_risk = (atr_ratio > 1.25) and not is_breaking

        industry = SYMBOL_INDUSTRY_MAP.get(symbol, "OTHER")
        ind_rank = IND_METRICS.get(industry, {"industry_rank": 999})["industry_rank"]
        fund_flow_aligned = is_breaking and (ind_rank <= 30) and MARKET_BREADTH["nifty_20ema_bullish"]

        # 8. STEALTH LINE CHECKER
        rs_line_nh = False
        if BENCHMARK_CLOSE is not None:
            b_aligned = BENCHMARK_CLOSE.reindex(c.index).ffill().bfill()
            rs_line = (c / b_aligned).dropna()
            if len(rs_line) >= 253:
                rs_line_nh = float(rs_line.iloc[-1]) >= float(rs_line.iloc[-253:-1].max())
        stealth_leader = rs_line_nh and (price < high_52w)

        # ====================================================
        # DECOUPLED MATRIX TAXONOMY (MAX 38 PTS)
        # ====================================================
        score = 0

        if stage == "STAGE_2": score += 3
        if trend_consistency >= 0.80: score += 3
        elif trend_consistency >= 0.70: score += 1

        if stealth_leader: score += 4
        elif rs_line_nh: score += 2
        if price >= high_52w: score += 4
        elif price >= pivot_45d: score += 2

        if rs_rating >= 95: score += 4
        elif rs_rating >= 90: score += 3
        elif rs_rating >= 80: score += 2

        if rs_mom_rank >= 95: score += 4
        elif rs_mom_rank >= 85: score += 3
        elif rs_mom_rank >= 70: score += 2

        if ind_rank <= 10: score += 4
        elif ind_rank <= 25: score += 3

        if liq_pct >= 90: score += 3
        elif liq_pct >= 70: score += 2

        if atr_ratio <= 0.65: score += 3
        elif atr_ratio <= 0.80: score += 1

        if vol_expansion_risk: score -= 3
        if dist_days_25 >= 4: score -= 3

        if is_breaking:
            score += 2 
            if close_pos >= 0.75: score += 1 
            if fund_flow_aligned: score += 3 
            
        if MARKET_BREADTH["regime"] == "SEVERE_WEAKNESS": return None 
        elif MARKET_BREADTH["regime"] == "DEFENSIVE": score = int(score * 0.75)

        if score >= 32: grade = "A+"
        elif score >= 26: grade = "A"
        elif score >= 18: grade = "B"
        else: return None

        # Setup Assignment
        setup = "🔥 ALIGNED EXPANSION" if fund_flow_aligned else ("🔥 BREAKOUT" if is_breaking else "BASE BUILDING")

        # ---------------------------------------------------------------------
        # RECONCILED STRUCTURAL EXPORT EXTENSIONS
        # ---------------------------------------------------------------------
        # Derive structural pivot prices matching context-dependent horizons
        pivot_target = round(pivot_45d, 2) if is_breaking else round(pivot_20d, 2)
        
        # Extrapolate dynamic Expected Days to Pivot metrics
        dist_to_pivot = ((pivot_target - price) / price) * 100.0 if pivot_target > price else 0.0
        edp_days = 1 if dist_to_pivot <= 1.5 else (2 if dist_to_pivot <= 3.5 else 3)
        edp_label = f"{edp_days} Trading Day" if edp_days == 1 else f"{edp_days} Trading Days"

        # Auto-generate precise trigger maps for downstream consumers
        clean_sym_name = symbol.replace(".NS", "")
        if is_breaking:
            actionable_trigger = f"🔥 ACTIVE TRIGGER - Buy breakout above ₹{pivot_target} on Vol > 1.8x"
        else:
            actionable_trigger = f"WATCH - Core setup consolidation near resistance line floor ₹{pivot_target}"

        return {
            "Ticker": symbol.replace(".NS", ""),
            "Price": round(price, 2),
            "Pivot": pivot_target,
            "Operational Classification Tier": f"Tier 1 — Ready to Monitor Daily" if grade in ["A+", "A"] else f"Tier 2 — Institutional Accumulation",
            "Opportunity": f"{round(score / 3.8, 1)}/10",
            "Readiness": f"{round(rs_rating / 10.0, 1)}/10",
            "Expected Days to Pivot (EDP)": edp_label,
            "14d ATR": f"{round(atr_14d_pct, 2)}%",
            "Actionable Operational Trigger": actionable_trigger,
            "Composite_Grade": score, # Satisfies trigger engine load constraints
            "Grade": grade,
            "Alpha": score,
            "Setup": setup,
            "RS Rnk": rs_rating,
            "Z-Mom %": rs_mom_rank,
            "Ind Rank": ind_rank,
            "Trnd Cons": round(trend_consistency, 2),
            "ATR Rat": round(atr_ratio, 2)
        }
    except: return None

# ============================================================================
# PROCESSING ENGINE EXECUTION
# ============================================================================
def run():
    print("=" * 150)
    print("🏆 HYBRID INSTITUTIONAL ALPHA SCANNER v24.0 [SOVEREIGN ENGINE]")
    print("=" * 150)

    symbols = load_symbols()
    if not symbols: return

    build_cache(symbols)
    precompute_metrics()

    comp = MARKET_BREADTH['composite']
    regime = MARKET_BREADTH['regime']
    gate = MARKET_BREADTH['liq_gate']
    print(f"\n🌍 COMPOSITE BREADTH INDEX: {comp:.1f} | Regime: {regime} | Adaptive Liq Gate: Top {100-gate:.0f}%")

    print("\n🔍 Scoring Universe Against Non-Collinear Alignment Protocol...")
    results = []
    with ThreadPoolExecutor(max_workers=30) as executor:
        for r in executor.map(analyze_stock, DATA_CACHE.keys()):
            if r: results.append(r)

    if not results:
        print("❌ No equities successfully graduated past the Sovereign Matrix standard today.")
        return

    out = pd.DataFrame(results).sort_values(by=["Alpha", "RS Rnk", "Z-Mom %"], ascending=False)
    pd.set_option("display.max_columns", None); pd.set_option("display.width", 250)
    
    print("\n" + out.head(50).to_string(index=False) + "\n" + "=" * 150)
    
    # Static filename export layer - completely removed time/date execution stamps
    output_file = "SOVEREIGN_ALPHA_V24.xlsx"
    with pd.ExcelWriter(output_file) as writer: 
        out.to_excel(writer, sheet_name="Master Alpha", index=False)
    print(f"📁 Institutional Execution Complete. Asset Registry Exported to → {output_file}")

if __name__ == "__main__": run()