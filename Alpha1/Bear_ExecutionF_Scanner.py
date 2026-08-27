# ============================================================
# Bear_ExecutionF_Scanner v16.5
# Enterprise Production Build — Live Fundamental Ingestion
# Robust Session Architecture + Outlier Clipping Engine
# Constrained MPO Optimizer + Unified Non-Distortive Horizons
# ============================================================

import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import time
import random
import json
import requests
from datetime import datetime
from sklearn.linear_model import Ridge
from scipy.optimize import minimize

warnings.filterwarnings("ignore")

# ============================================================
# MASTER SYSTEM CONFIGURATIONS
# ============================================================
CSV_FILE = "NSE_EQ.csv"        
LOOKBACK = "2y"               # Two-year window guarantees deep history for 252d metrics
BENCHMARK = "^NSEI"

MIN_PRICE = 20
MIN_VOLUME = 50000            # Preserves structural access to small-cap turnarounds safely
MAX_SCAN = 2500
MAX_RETRIES = 3

# UNIFIED TIME HORIZON MATRIX
PRIMARY_WINDOW = 252          # 1-Year Primary Horizon (Volatility, Alpha, Drawdowns)
SECONDARY_WINDOW = 63         # 3-Month Secondary Horizon (Support Floors, Base Tightness)

GATE_MIN_DRAWDOWN = 20.0       
GATE_MAX_RSI = 58.0            
TARGET_RECOVERY_ARC = 0.50

RIDGE_ALPHA_SHRINKAGE = 1.0   # L2 Regularization penalty strength for factor shrinkage
BETA_SHRINKAGE_FACTOR = 0.70  # Vasicek alpha weight assigned to raw asset beta
RISK_AVERSION_LAMBDA = 1.5    # Lambda risk aversion multiplier for mean-variance optimization

# ENTERPRISE CONCENTRATION SAFETY CONSTRAINTS
MAX_ASSET_ALLOCATION_CEILING = 15.0  # Hard 15% maximum capital cap constraint per single asset position
MAX_SECTOR_WEIGHT_CEILING = 25.0     # Hard 25% maximum cumulative weight constraint per sector bucket
MIN_POSITION_WEIGHT_FLOOR = 1.0      # Hard 1% minimum position threshold if allocated capital is passed

# DATA INTEGRITY FILTER PARAMETERS
MIN_SIGNAL_VALIDITY_THRESHOLD = 40.0  # Keeps assets with verifiable core financial reporting disclosure

# ============================================================
# INITIALIZE ROBUST UNIFIED NETWORK SESSION (FIXES HTTP 400/429)
# ============================================================
HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
})

# ============================================================
# DATA PIPELINE UTILITIES & LOCAL METADATA INGESTION
# ============================================================

def load_universe_metadata():
    print("\n📡 Ingesting Local Universe Table & Standardized Financial Matrices...")
    try:
        df = pd.read_csv(CSV_FILE)
        cols = [c.upper().strip() for c in df.columns]
        if "SYMBOL" not in cols:
            raise Exception("Required column 'SYMBOL' missing from source CSV file.")
        
        symbol_col = df.columns[cols.index("SYMBOL")]
        
        metadata_registry = {}
        for _, row in df.dropna(subset=[symbol_col]).iterrows():
            s = str(row[symbol_col]).upper().strip()
            if len(s) < 2 or any(x in s for x in ["/", "\\", " ", "&", "*"]) or "DUMMY" in s:
                continue
            if not s.endswith(".NS"):
                s += ".NS"

            # Register valid tracking symbols for Phase 1 technical screening
            metadata_registry[s] = True

        print(f"✅ Active Database Mapped: {len(metadata_registry)} verified symbols initialized from CSV ticker frame.")
        return metadata_registry
    except Exception as e:
        print(f" ❌ Critical Ingestion Failure: Local data metrics format invalid -> {e}")
        return {}

def fetch_dynamic_fundamentals(symbol):
    """Queries live exchange databases using robust sessions to harvest factor vectors."""
    try:
        ticker = yf.Ticker(symbol, session=HTTP_SESSION)
        info = ticker.info
        if not info or not isinstance(info, dict):
            return None
            
        sector = info.get('sector', 'Unclassified')
        
        # Parse return metrics
        roe = info.get('returnOnEquity')
        roe_val = float(roe) * 100.0 if roe is not None else np.nan
        
        # Parse margin matrices
        margin = info.get('operatingMargins')
        margin_val = float(margin) * 100.0 if margin is not None else np.nan
        
        # Adaptive Debt Ratio Parsing
        de = info.get('debtToEquity')
        if de is not None:
            de_val = float(de)
            if de_val > 10.0:  # If reported as percentage (e.g. 55%), normalize to scale ratio (0.55)
                de_val = de_val / 100.0
        else:
            de_val = np.nan
            
        # Parse revenue & earnings growth factors
        rev_growth = info.get('revenueGrowth')
        sales_acc = float(rev_growth) * 100.0 if rev_growth is not None else np.nan
        
        eps_growth = info.get('earningsGrowth')
        eps_acc = float(eps_growth) * 100.0 if eps_growth is not None else np.nan
        
        # Compute alternative surprise yield profile via trailing PE metrics
        trailing_pe = info.get('trailingPE')
        surprise_val = (100.0 / float(trailing_pe)) if trailing_pe else 0.0
        
        # Categorical BFSI Flag Assignment
        sec_upper = sector.upper()
        if any(x in sec_upper for x in ["BANK", "FINANC", "BFSI", "INSURANCE", "BROKER", "INVEST", "HOLDING"]):
            is_bfsi = 1
        else:
            is_bfsi = 0
        
        # Cash Flow Purity Verification Check
        fcf = info.get('freeCashflow')
        fcf_bad = True if (fcf is not None and float(fcf) < 0) else False
        
        # Calculate Signal Validity score based on active data presence
        tracked_fields = [roe, margin, de, rev_growth, eps_growth]
        valid_count = sum(1 for f in tracked_fields if f is not None)
        signal_validity = (valid_count / len(tracked_fields)) * 100.0
        
        return {
            "Sector": sector,
            "ROE%": roe_val,
            "Debt_Equity": de_val,
            "Operating_Margins%": margin_val,
            "EPS_Surprise%": surprise_val,
            "Sales_Acceleration%": sales_acc,
            "Earnings_Acceleration%": eps_acc,
            "Is_BFSI": is_bfsi,
            "fcf_bad": fcf_bad,
            "Signal_Validity%": round(signal_validity, 1)
        }
    except Exception:
        return None

def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def nearest_fib(price, high, low):
    diff = high - low
    if diff <= 0: return "0.0%"
    fibs = {
        "23.6%": high - diff * 0.236,
        "38.2%": high - diff * 0.382,
        "50.0%": high - diff * 0.500,
        "61.8%": high - diff * 0.618,
        "78.6%": high - diff * 0.786,
    }
    return min(fibs.items(), key=lambda x: abs(price - x[1]))[0]

def safe_download(symbol):
    for attempt in range(MAX_RETRIES):
        try:
            df = yf.download(symbol, period=LOOKBACK, interval="1d", auto_adjust=True, progress=False, threads=False, session=HTTP_SESSION)
            if df is None or df.empty:
                time.sleep(0.1)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            if len(df) < 260: return None
            return df
        except Exception:
            time.sleep(0.1)
    return None

# ============================================================
# PHASE 1: TECHNICAL ATTRIBUTE PROFILE HARVESTER
# ============================================================

def extract_technical_profile(symbol, nifty_df, nifty_returns):
    try:
        df = safe_download(symbol)
        if df is None: return None

        raw_vol = df["Volume"].dropna()
        avg_vol20 = float(raw_vol.tail(20).mean()) if len(raw_vol) >= 20 else 0.0
        if pd.isna(avg_vol20) or avg_vol20 < MIN_VOLUME: return None

        common_idx = df.index.intersection(nifty_df.index)
        if len(common_idx) < PRIMARY_WINDOW: return None  
        
        df_aligned = df.loc[common_idx].sort_index()
        close = df_aligned["Close"]
        high = df_aligned["High"]
        low = df_aligned["Low"]

        entry = float(close.iloc[-1])
        if entry < MIN_PRICE: return None

        high_52w = float(high.tail(PRIMARY_WINDOW).max())
        low_52w = float(low.tail(PRIMARY_WINDOW).min())
        if high_52w <= low_52w: return None
        drawdown_pct = ((high_52w - entry) / high_52w) * 100

        daily_returns = np.log(close / close.shift(1)).dropna()
        if len(daily_returns) < PRIMARY_WINDOW: return None
        
        total_vol = daily_returns.tail(PRIMARY_WINDOW).std() * np.sqrt(252)
        downside_returns = daily_returns.tail(PRIMARY_WINDOW).clip(upper=0)
        # 🎯 TYPO FIXED HERE: Restored full expression alignment structure safely
        downside_deviation = downside_returns.std() * np.sqrt(252)
        if pd.isna(downside_deviation) or pd.isna(total_vol) or total_vol <= 0 or downside_deviation <= 0: return None

        stock_rets = daily_returns.tail(PRIMARY_WINDOW)
        nifty_rets = nifty_returns.reindex(stock_rets.index).fillna(0.0)
        cov_matrix = np.cov(stock_rets, nifty_rets)
        raw_beta = cov_matrix[0][1] / cov_matrix[1][1] if (len(cov_matrix) > 1 and cov_matrix[1][1] > 1e-9) else 1.0
        shrunk_beta = (BETA_SHRINKAGE_FACTOR * raw_beta) + ((1.0 - BETA_SHRINKAGE_FACTOR) * 1.0)

        tracking_risk_unit = total_vol * np.sqrt(1.0 + (shrunk_beta ** 2))

        dates = df_aligned.index
        years_delta = (dates[-1] - dates[-PRIMARY_WINDOW]).days / 365.25
        if years_delta <= 0: return None

        stock_hist = float(close.iloc[-PRIMARY_WINDOW])
        nifty_hist = float(nifty_df["Close"].iloc[-PRIMARY_WINDOW])
        if stock_hist <= 0 or nifty_hist <= 0: return None
        
        cagr_stock = np.log(entry / stock_hist) / years_delta
        cagr_nifty = np.log(float(nifty_df["Close"].iloc[-1]) / nifty_hist) / years_delta
        true_sortino_ratio = (cagr_stock - cagr_nifty) / downside_deviation

        recent_low_63d = float(low.tail(SECONDARY_WINDOW).min())
        distance_from_support = ((entry - recent_low_63d) / entry) * 100
        tightness_63d = (high.tail(SECONDARY_WINDOW).max() - low.tail(SECONDARY_WINDOW).min()) / entry

        rsi_series = calculate_rsi(close)
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.isna().all() else 50.0
        fib = nearest_fib(entry, high_52w, low_52w)
        
        sl = round(recent_low_63d * 0.97, 2)
        target1 = round(entry + (high_52w - entry) * TARGET_RECOVERY_ARC, 2)
        risk = entry - sl
        rr = round((target1 - entry) / risk, 2) if (risk > 1e-4) else 0.0

        return {
            "Stock": symbol, "Price": entry, "Drawdown%": round(drawdown_pct, 2),
            "Distance_Support%": round(distance_from_support, 2), "RSI": round(rsi, 1), 
            "Nearest Fib": fib, "True_Sortino_Alpha": true_sortino_ratio, "tightness_63d": round(tightness_63d, 3),
            "SL": sl, "Target 1": target1, "R:R": rr, "Tracking_Risk": tracking_risk_unit, "Beta_Nifty": round(shrunk_beta, 2),
            "Blended_Alpha_Raw": cagr_stock - cagr_nifty,
            "Returns_Series": json.dumps(stock_rets.tail(PRIMARY_WINDOW).tolist())
        }
    except Exception:
        return None

# ============================================================
# MAIN COHORT DISPATCH ALLOCATOR ENGINE
# ============================================================

def run_pipeline():
    print("\n=================================================================")
    print("🚀 SOVEREIGN FACTOR RISK ALLOCATOR ENGINE v16.5")
    print("=================================================================")

    metadata_registry = load_universe_metadata()
    if not metadata_registry:
        return

    nifty_df = yf.download(BENCHMARK, period=LOOKBACK, interval="1d", auto_adjust=True, progress=False, session=HTTP_SESSION)
    if isinstance(nifty_df.columns, pd.MultiIndex): nifty_df.columns = nifty_df.columns.get_level_values(0)
    nifty_df = nifty_df.dropna()
    nifty_returns = np.log(nifty_df["Close"] / nifty_df["Close"].shift(1)).dropna()

    # QUAD-STATE MACRO REGIME WEIGHTING CONFIGURATIONS
    nifty_close = nifty_df["Close"]
    trend_score = 1 if nifty_close.iloc[-1] >= nifty_close.rolling(252).mean().iloc[-1] else -1
    momentum_score = 1 if nifty_close.iloc[-1] >= nifty_close.rolling(63).mean().iloc[-1] else -1
    vol_score = -1 if (nifty_returns.tail(30).std() * np.sqrt(252)) > 0.18 else 1
    regime_score_index = trend_score + momentum_score + vol_score

    if regime_score_index <= -1:
        regime_status = "🐻 CONTRACTION REGIME (Severe Balance Sheet Safety & Deep Reversion Rules Forced)"
        w_safety, w_growth, w_reversion, w_momentum = 0.55, 0.05, 0.35, 0.05
    elif regime_score_index == 1:
        regime_status = "🟡 DISTRIBUTION REGIME (Defensive Structural Allocations Imposed)"
        w_safety, w_growth, w_reversion, w_momentum = 0.40, 0.25, 0.25, 0.10
    elif regime_score_index >= 2:
        regime_status = "🐂 EXPANSION REGIME (Bull Acceleration Factor Scaling Active)"
        w_safety, w_growth, w_reversion, w_momentum = 0.15, 0.55, 0.10, 0.20
    else:
        regime_status = "🟢 RECOVERY REGIME (Early Structural Mean Reversion Active)"
        w_safety, w_growth, w_reversion, w_momentum = 0.25, 0.20, 0.45, 0.10

    print(f"📊 Active Market State Determined: {regime_status}")
    print(f"⚖️ Applied Blended Weights: {int(w_safety*100)}% BS Safety / {int(w_growth*100)}% Growth Accel / {int(w_reversion*100)}% Reversion / {int(w_momentum*100)}% Residual RS")

    print(f"\n🔍 Phase 1: Processing Synchronous Technical Harvester over {len(metadata_registry)} Tickers...")
    tech_results = []
    start_time = time.time()

    for i, symbol in enumerate(metadata_registry.keys()):
        profile = extract_technical_profile(symbol, nifty_df, nifty_returns)
        if profile: 
            tech_results.append(profile)
        if i % 100 == 0 and i != 0:
            print(f"   ⏳ Scanned {i}/{len(metadata_registry)} | Active Target Candidates: {len(tech_results)} | {round(time.time() - start_time, 1)}s")
        time.sleep(random.uniform(0.005, 0.015))

    if not tech_results:
        print("⚠️ Technical Failure: Zero anomalies recorded."); return
    tech_df = pd.DataFrame(tech_results)

    print("\n🧮 Phase 2: Generating Pre-Gate Cross-Universe 12M Momentum Percentile Matrix...")
    tech_df["Universe_RS_Percentile"] = (tech_df["Blended_Alpha_Raw"].rank(pct=True) * 100.0).round(1)

    print("🎯 Phase 2b: Running Contrarian Filter Rules...")
    gate_mask = (tech_df["Drawdown%"] >= GATE_MIN_DRAWDOWN) & (tech_df["RSI"] <= GATE_MAX_RSI)
    distilled_df = tech_df[gate_mask].reset_index(drop=True)
    
    print(f"✅ Pass Verification: {len(distilled_df)} companies successfully isolated for multi-factor matrix combination.")
    if distilled_df.empty:
        print("⚠️ Exception Handling: Zero tickers matched workspace rules."); return

    # ========================================================
    # PHASE 3: DYNAMIC ACCELERATION HARVESTER
    # ========================================================
    print("\n⚡ Phase 3: Dynamic Network Harvesting of Fundamental Accounting Metrics...")
    final_records = []
    dropped_clones_count = 0
    total_to_fetch = len(distilled_df)
    print(f"   📥 Fetching live cross-sectional fundamentals for {total_to_fetch} isolated assets...")
    
    for idx, row in distilled_df.iterrows():
        symbol = row["Stock"]
        fundamentals = fetch_dynamic_fundamentals(symbol)
        
        if fundamentals and fundamentals["Signal_Validity%"] >= MIN_SIGNAL_VALIDITY_THRESHOLD:
            combined_dict = {**row.to_dict(), **fundamentals}
            final_records.append(combined_dict)
        else:
            dropped_clones_count += 1
            
        if (idx + 1) % 50 == 0 or (idx + 1) == total_to_fetch:
            print(f"   ⏳ Progress: {idx + 1}/{total_to_fetch} assets mapped successfully.")
            
    if not final_records:
        print("⚠️ Matrix Invalidation: Zero corporate safety profiles survived dynamic filter gates."); return
    master_df = pd.DataFrame(final_records)
    print(f"✅ Data Integrity Fence: Kept {len(master_df)} verified profiles, dropped {dropped_clones_count} incomplete indices.")

    # ========================================================
    # PHASE 4: THE CONTINUOUS PRE-SCORING COMPONENT STANDARDIZATION MATRIX
    # ========================================================
    print("🧮 Phase 4: Constructing Continuous Winsorized Pre-Scoring Factor Space...")
    
    if "Is_BFSI" not in master_df.columns:
        master_df["Is_BFSI"] = 0

    for fill_col in ["ROE%", "Operating_Margins%", "Debt_Equity", "Sales_Acceleration%", "Earnings_Acceleration%", "EPS_Surprise%", "Is_BFSI"]:
        median_val = master_df[fill_col].median()
        if pd.isna(median_val):
            median_val = 0.0
        master_df[fill_col] = master_df[fill_col].fillna(median_val)

    sub_components = [
        "Drawdown%", "RSI", "tightness_63d", "ROE%", "Operating_Margins%", 
        "Debt_Equity", "EPS_Surprise%", "Sales_Acceleration%", "Earnings_Acceleration%", "Universe_RS_Percentile", "True_Sortino_Alpha"
    ]
    for sub_col in sub_components:
        p1, p99 = master_df[sub_col].quantile(0.01), master_df[sub_col].quantile(0.99)
        clipped = np.clip(master_df[sub_col], p1, p99)
        mean, std = clipped.mean(), clipped.std()
        z_score_raw = (clipped - mean) / (std if std > 1e-9 else 1.0)
        master_df[f"{sub_col}_Z"] = np.clip(z_score_raw, -3.0, 3.0)

    # 🧠 DECOUPLED ALPHA SCORE STRUCTURING
    master_df["Raw_Balance_Sheet_Safety_Z"] = (
        (master_df["ROE%_Z"] * 0.40) + 
        (master_df["Operating_Margins%_Z"] * 0.40) + 
        ((-master_df["Debt_Equity_Z"]) * 0.20)
    )
    master_df["Raw_Growth_Acceleration_Z"] = (
        (master_df["Earnings_Acceleration%_Z"] * 0.45) + 
        (master_df["Sales_Acceleration%_Z"] * 0.35) + 
        (master_df["EPS_Surprise%_Z"] * 0.20)
    )
    master_df["Raw_Reversion_Z"] = (
        (master_df["Drawdown%_Z"] * 0.40) + 
        ((-master_df["RSI_Z"]) * 0.40) + 
        ((-master_df["tightness_63d_Z"]) * 0.20)
    )
    master_df["Raw_Momentum_Z"] = (master_df["Universe_RS_Percentile_Z"] * 0.60) + (master_df["True_Sortino_Alpha_Z"] * 0.40)

    for final_z in ["Raw_Balance_Sheet_Safety_Z", "Raw_Growth_Acceleration_Z", "Raw_Reversion_Z", "Raw_Momentum_Z"]:
        mean, std = master_df[final_z].mean(), master_df[final_z].std()
        normalized_composite = (master_df[final_z] - mean) / (std if std > 1e-9 else 1.0)
        master_df[final_z] = np.clip(normalized_composite, -3.0, 3.0)

    # ========================================================
    # PHASE 5: REGULARIZED RIDGE FACTOR ORTHOGONALIZATION
    # ========================================================
    print("🧮 Phase 5: Executing Regularized Cross-Sectional Ridge Orthogonalization...")
    X_reg = master_df[["Raw_Balance_Sheet_Safety_Z", "Raw_Growth_Acceleration_Z", "Raw_Reversion_Z"]].fillna(0.0).values
    Y_reg = master_df["Raw_Momentum_Z"].fillna(0.0).values
    try:
        ridge_model = Ridge(alpha=RIDGE_ALPHA_SHRINKAGE)
        ridge_model.fit(X_reg, Y_reg)
        master_df["Orthogonal_Momentum_Z"] = Y_reg - ridge_model.predict(X_reg)
        print(rf"🎯 Decorrelation Complete: Ridge regularizer ($\lambda$={RIDGE_ALPHA_SHRINKAGE}) successfully extracted pure residual momentum.")
    except Exception as e:
        print(f"⚠️ Regularization Warning: Falling back to standardized inputs ({e})")
        master_df["Orthogonal_Momentum_Z"] = Y_reg

    # Unified Master Blended Alpha Scoring Equation via Realigned Weights Matrix
    master_df["Blended Score"] = (
        (master_df["Raw_Balance_Sheet_Safety_Z"] * w_safety) + 
        (master_df["Raw_Growth_Acceleration_Z"] * w_growth) + 
        (master_df["Raw_Reversion_Z"] * w_reversion) + 
        (master_df["Orthogonal_Momentum_Z"] * w_momentum)
    ).round(2)
    master_df["Blended Score"] = master_df["Blended Score"].fillna(0.0)

    # ========================================================
    # PHASE 6: 5-TIER COHORT QUALITY SEPARATION MATRIX
    # ========================================================
    print("🧮 Phase 6: Organizing Vetted Quality Turnaround Cohorts...")
    separation_statuses = []
    for _, row in master_df.iterrows():
        roe = row.get("ROE%", 0.0)
        de = row.get("Debt_Equity", 0.0)
        is_bfsi = int(row.get("Is_BFSI", 0))
        safety_z = row.get("Raw_Balance_Sheet_Safety_Z", 0.0)
        growth_z = row.get("Raw_Growth_Acceleration_Z", 0.0)
        fcf_bad = bool(row.get("fcf_bad", False))
        
        s_roe, s_de = float(roe) if pd.notna(roe) else 0.0, float(de) if pd.notna(de) else 0.0
        rs_pct = float(row.get("Universe_RS_Percentile", 50.0))
        drawdown_val = float(row.get("Drawdown%", 0.0))
        sales_acc = float(row.get("Sales_Acceleration%", 0.0))
        eps_acc = float(row.get("Earnings_Acceleration%", 0.0))
        
        if is_bfsi == 1: 
            is_trap = (safety_z <= -1.2) or (s_roe < 11.0)
        else: 
            is_trap = (safety_z <= -1.2) or ((s_roe < 11.0) & (s_de > 1.6)) or (fcf_bad and safety_z <= -0.4)

        is_emerging_leader = (rs_pct >= 82.0) and (eps_acc > 2.0) and (sales_acc > 2.0) and (15.0 <= drawdown_val <= 40.0) and (not is_trap)
        is_elite = (safety_z >= 0.8) and (growth_z >= 0.3) and (not is_trap)
        is_high_quality = (safety_z >= 0.2) and (not is_trap)

        if is_trap: separation_statuses.append("⚠️ VALUE TRAP LIKELY")
        elif is_emerging_leader: separation_statuses.append("🚀 EMERGING LEADER")
        elif is_elite: separation_statuses.append("🔥 ELITE DISTRESS")
        elif is_high_quality: separation_statuses.append("🔥 HIGH-QUALITY DISTRESS")
        else: separation_statuses.append("🟢 MEDIUM-QUALITY DISTRESS")

    master_df["Quality Separation Status"] = separation_statuses
    priority_map = {"🚀 EMERGING LEADER": 5, "🔥 ELITE DISTRESS": 4, "🔥 HIGH-QUALITY DISTRESS": 3, "🟢 MEDIUM-QUALITY DISTRESS": 2, "⚠️ VALUE TRAP LIKELY": 1}
    master_df["Priority_Sort_Index"] = master_df["Quality Separation Status"].map(priority_map)

    # ============================================================
    # PHASE 7: CONSTRAINED MEAN-VARIANCE PORTFOLIO OPTIMIZER ENGINE
    # ============================================================
    print("💼 Phase 7: Building Institutional Constrained Portfolio Optimizer Matrix...")
    allocator_mask = master_df["Priority_Sort_Index"] > 1
    master_df["Target_Allocation%"] = 0.0
    
    if allocator_mask.any():
        sub_df = master_df[allocator_mask].copy()
        
        if len(sub_df) > 40:
            sub_df = sub_df.sort_values(by="Blended Score", ascending=False).head(40)
            
        n_assets = len(sub_df)
        
        returns_dict = {row["Stock"]: pd.Series(json.loads(row["Returns_Series"])) for _, row in sub_df.iterrows()}
        cluster_returns_df = pd.DataFrame(returns_dict).fillna(0.0)
        
        optimized_covariance_matrix = cluster_returns_df.cov().values
        alpha_utility_vectors = sub_df["Blended Score"].values
        sectors_list = sub_df["Sector"].tolist()
        unique_sectors = list(set(sectors_list))
        
        def mean_variance_objective(weights):
            portfolio_alpha = np.dot(weights, alpha_utility_vectors)
            portfolio_variance = np.dot(weights.T, np.dot(optimized_covariance_matrix, weights))
            return -1.0 * (portfolio_alpha - (RISK_AVERSION_LAMBDA * portfolio_variance))

        constraints = []
        constraints.append({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}) 
        
        for sector in unique_sectors:
            sector_indices = [idx for idx, sec in enumerate(sectors_list) if sec == sector]
            constraints.append({
                'type': 'ineq',
                'fun': lambda w, idxs=sector_indices: (MAX_SECTOR_WEIGHT_CEILING / 100.0) - np.sum(w[idxs])
            })
            
        bounds = [(MIN_POSITION_WEIGHT_FLOOR / 100.0, MAX_ASSET_ALLOCATION_CEILING / 100.0) for _ in range(n_assets)]
        initial_weights = np.ones(n_assets) / n_assets
        
        try:
            optimization_result = minimize(
                mean_variance_objective, 
                initial_weights, 
                method='SLSQP', 
                bounds=bounds, 
                constraints=constraints,
                options={'maxiter': 200, 'ftol': 1e-6}
            )
            
            if optimization_result.success: final_alloc_weights = optimization_result.x
            else: final_alloc_weights = initial_weights
        except Exception:
            final_alloc_weights = initial_weights
            
        sub_df["Target_Allocation%"] = np.round(final_alloc_weights * 100.0, 2)
        master_df.update(sub_df[["Target_Allocation%"]])

    # Unified alpha reporting column matrix definition map
    display_cols = [
        "Stock", "Price", "Drawdown%", "Distance_Support%", "RSI", "True_Sortino_Alpha", "Beta_Nifty",
        "ROE%", "Debt_Equity", "Operating_Margins%", "Sales_Acceleration%", "Earnings_Acceleration%", "EPS_Surprise%", 
        "Signal_Validity%", "Target_Allocation%", "Blended Score", "Quality Separation Status"
    ]
    
    final_output = master_df.sort_values(by=["Priority_Sort_Index", "Blended Score"], ascending=[False, False])
    final_output = final_output[display_cols].reset_index(drop=True)

    # ========================================================
    # REPORT ARCHIVING AND MULTI-SHEET WORKBOOK EXPORT
    # ========================================================
    output_file = f"SOVEREIGN_FACTOR_MATRIX_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    with pd.ExcelWriter(output_file) as writer:
        final_output.to_excel(writer, sheet_name="Master Allocation Cohort", index=False)
        final_output[final_output["Quality Separation Status"] == "🚀 EMERGING LEADER"].to_excel(writer, sheet_name="Emerging Leaders", index=False)
        final_output[final_output["Quality Separation Status"] == "🔥 ELITE DISTRESS"].to_excel(writer, sheet_name="Elite Allocation Targets", index=False)
        final_output[final_output["Quality Separation Status"] == "🔥 HIGH-QUALITY DISTRESS"].to_excel(writer, sheet_name="High-Quality Distress", index=False)
        final_output[final_output["Quality Separation Status"] == "⚠️ VALUE TRAP LIKELY"].to_excel(writer, sheet_name="Value Traps - Avoid", index=False)

    print("\n========= SYSTEM PREVIEW (CONSTRAINED MEAN-VARIANCE PORTFOLIO OPTIMIZATION) =========")
    print(final_output.head(25).to_string(index=False))
    print(f"\n📁 Enterprise Multi-Constraint Portfolio Capital Matrix Saved Safely → {output_file}\n")

if __name__ == "__main__":
    run_pipeline()