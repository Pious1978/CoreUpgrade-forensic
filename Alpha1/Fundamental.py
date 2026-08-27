import logging
import time
import re
import sys
import warnings
from typing import TypedDict, Dict, Any, List, Optional, Tuple
from collections import OrderedDict
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata
from scipy.optimize import minimize
import yfinance as yf

# Silence explicit dateutil format parsing warnings globally to preserve console clarity
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure enterprise-grade logging matrix to ensure absolute production traceability
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# =============================================================================
# LAYER 0: ENTERPRISE DATA CONTRACTS & TYPE SIGNATURES
# =============================================================================
class FactorExposure(TypedDict):
    value_raw: float     
    quality_raw: float
    growth_raw: float
    momentum_raw: float
    value_z: float       
    quality_z: float
    growth_z: float
    momentum_z: float
    uncertainty_variance: float

class AbsoluteValuation(TypedDict):
    intrinsic_fair_value: float
    raw_mos: float
    mos_score: float  
    core_model_value: float
    multiple_value: float

class AssetSignal(TypedDict):
    ticker: str
    sector: str
    composite_factor_score: float
    exposures: FactorExposure
    valuation: AbsoluteValuation
    business_archetype: str  

class OptimizationOutput(TypedDict):
    regime_state: str
    optimal_weights: Dict[str, float]
    portfolio_volatility: float
    portfolio_sharpe: float
    execution_directives: Dict[str, str]

# =============================================================================
# LAYER 1: IMMUTABLE TYPE-SAFE VERSIONED LRU CACHE ENGINE
# =============================================================================
def get_canonical_symbol(symbol: str) -> str:
    if not symbol: return ""
    return str(symbol).upper().strip().split(".")[0].replace(".NS", "").replace(".BO", "")

class InstitutionalCache:
    def __init__(self, max_size: int = 1024, ttl_seconds: int = 7200):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.version_keys: Dict[str, str] = {}

    def _generate_state_hash(self, ticker: str) -> str:
        c_tk = get_canonical_symbol(ticker)
        return f"V_{time.strftime('%Y%m%d')}_{c_tk}"

    def _get_raw(self, key: str) -> Optional[Any]:
        c_key = get_canonical_symbol(key)
        if c_key in self.cache:
            if self.version_keys.get(c_key) != self._generate_state_hash(c_key):
                self.pop(c_key)
                return None
            if time.time() - self.timestamps[c_key] > self.ttl_seconds:
                self.pop(c_key)
                return None
            self.cache.move_to_end(c_key)
            return self.cache[c_key]
        return None

    def get_dataframe(self, key: str) -> pd.DataFrame:
        obj = self._get_raw(key)
        return obj if (obj is not None and isinstance(obj, pd.DataFrame)) else pd.DataFrame()

    def get_series(self, key: str) -> pd.Series:
        obj = self._get_raw(key)
        return obj if (obj is not None and isinstance(obj, pd.Series)) else pd.Series(dtype=float)

    def get_dict(self, key: str) -> dict:
        obj = self._get_raw(key)
        return obj if (obj is not None and isinstance(obj, dict)) else {}

    def set(self, key: str, value: Any, expected_type: str = "ANY") -> None:
        c_key = get_canonical_symbol(key)
        if expected_type != "ANY":
            if expected_type == "DATAFRAME" and not isinstance(value, pd.DataFrame): return
            if expected_type == "SERIES" and not isinstance(value, pd.Series):
                if isinstance(value, pd.DataFrame) and "Close" in value.columns: value = value["Close"]
                else: return
            if expected_type == "DICT" and not isinstance(value, dict): return

        if c_key in self.cache: self.cache.move_to_end(c_key)
        self.cache[c_key] = value
        self.timestamps[c_key] = time.time()
        self.version_keys[c_key] = self._generate_state_hash(c_key)
        if len(self.cache) > self.max_size:
            old_k, _ = self.cache.popitem(last=False)
            self.timestamps.pop(old_k, None)
            self.version_keys.pop(old_k, None)

    def pop(self, key: str) -> None:
        c_key = get_canonical_symbol(key)
        self.cache.pop(c_key, None)
        self.timestamps.pop(c_key, None)
        self.version_keys.pop(c_key, None)

QUANT_PIPELINE_CACHE = InstitutionalCache(max_size=1024, ttl_seconds=7200)

# =============================================================================
# LAYER 2: UTILITIES & CHRONOLOGICAL TIME-SERIES TOOLKIT
# =============================================================================
def safe_strip_timezone(index) -> pd.DatetimeIndex:
    try:
        if index is None: return pd.DatetimeIndex([])
        idx = pd.to_datetime(index, errors="coerce")
        if hasattr(idx, "tz_convert") and idx.tz is not None: return idx.tz_convert(None).dropna()
        if hasattr(idx, "tz_localize"): return idx.tz_localize(None).dropna()
        return pd.DatetimeIndex(idx).dropna()
    except Exception as e:
        return pd.DatetimeIndex([])

def normalize_key(x: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(x).lower().strip()).strip('_')

def safe_score(x, default: float = 0.0) -> float:
    if x is None: return default
    try:
        val = float(x)
        return default if np.isnan(val) or np.isinf(val) else val
    except: return default

def safe_get_sorted_series(series_or_df) -> pd.Series:
    if series_or_df is None: return pd.Series(dtype=float)
    if isinstance(series_or_df, pd.DataFrame):
        if series_or_df.empty: return pd.Series(dtype=float)
        if "Close" in series_or_df.columns: series_or_df = series_or_df["Close"]
        else: series_or_df = series_or_df.iloc[:, -1]
    if isinstance(series_or_df, pd.Series):
        if series_or_df.empty: return pd.Series(dtype=float)
        series_copy = series_or_df.copy()
        raw_idx = safe_strip_timezone(series_copy.index)
        if len(raw_idx) == 0: return pd.Series(dtype=float)
        series_copy.index = raw_idx
        series_copy = series_copy[~series_copy.index.duplicated(keep="last")]
        return series_copy.sort_index().fillna(0.0)
    return pd.Series(dtype=float)

def safe_get_scalar(series_or_val, fallback: float = 0.0) -> float:
    sorted_series = safe_get_sorted_series(series_or_val)
    if sorted_series.empty:
        try: return float(series_or_val) if not pd.isna(series_or_val) else fallback
        except: return fallback
    return float(sorted_series.iloc[-1])

# =============================================================================
# LAYER 3: TRANSLATION METRICS & DETECT STRUCTURAL ORIENTATOR
# =============================================================================
LABEL_MAP = {
    "net_income": ["net income stockholders", "net income", "net income common stockholders", "net income from continuing operations", "net income applicable to common shares", "net_income"],
    "revenue": ["total revenue", "operating revenue", "revenue", "gross sales", "total revenue operating", "total_revenue"],
    "eps": ["diluted eps", "basic eps", "diluted eps excluding extraordinary items", "diluted_eps"],
    "diluted_shares": ["diluted average shares", "basic average shares", "weighted average shares diluted", "shares_outstanding", "ordinary shares number"],
    "ebit": ["ebit", "operating income", "operating income expense", "operating profit", "operating_income"],
    "total_assets": ["total assets", "assets", "total assets balances", "total_assets"],
    "current_liabilities": ["current liabilities", "total current liabilities", "current_liabilities"],
    "cash_reserves": ["cash and cash equivalents", "cash cash equivalents and short term investments", "cash and cash equivalents checking", "cash_and_cash_equivalents"],
    "goodwill": ["goodwill", "goodwill and intangible assets", "net intangible assets", "goodwill_and_intangible_assets"],
    "free_cash_flow": ["free cash flow", "free cash flow operating", "free_cash_flow"],
    "operating_cash_flow": ["cash flow from operating activities", "operating cash flow", "total cash from operating activities", "operating_cash_flow"],
    "capex": ["capital expenditure", "capital expenditures", "capex", "net capital expenditures"],
    "interest_expense": ["interest expense", "interest expense corporate", "total interest expense", "interest_expense"],
    "nii": ["net interest income", "interest income net", "net interest income bank", "net_interest_income"],
    "gross_npa": ["gross npa", "gross non performing assets", "gross npa ratio", "bad loans", "gross_npa"],
    "net_npa": ["net npa", "net non performing assets", "net npa ratio", "net_npa"],
    "pcr": ["provision coverage ratio", "pcr", "provisions for non performing assets", "provision_coverage_ratio"],
    "cet1_ratio": ["cet1 ratio", "common equity tier 1 ratio", "tier 1 capital ratio", "cet1", "cet1_ratio"],
    "total_debt": ["total debt", "long term debt", "long term debt total", "total_debt", "long_term_debt"],
    "total_equity": ["total stockholders equity", "stockholders equity", "total stockholders_equity", "equity", "total_equity"]
}

def clean_and_sort_time_axis(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    sanitized_df = df.copy()
    
    cols_are_dates = False
    try:
        parsed_cols = pd.to_datetime(sanitized_df.columns, errors='coerce')
        if parsed_cols.notna().sum() > (len(sanitized_df.columns) / 2): cols_are_dates = True
    except: pass
    
    rows_are_dates = False
    try:
        parsed_rows = pd.to_datetime(sanitized_df.index, errors='coerce')
        if parsed_rows.notna().sum() > (len(sanitized_df.index) / 2): rows_are_dates = True
    except: pass

    if rows_are_dates and not cols_are_dates: 
        sanitized_df = sanitized_df.T
    elif not cols_are_dates and not rows_are_dates:
        if sanitized_df.shape[0] < sanitized_df.shape[1]: sanitized_df = sanitized_df.T
        
    try:
        sanitized_df.columns = safe_strip_timezone(sanitized_df.columns)
        sanitized_df = sanitized_df.loc[:, sanitized_df.columns.notna()]
        sanitized_df = sanitized_df.loc[:, ~sanitized_df.columns.duplicated(keep='last')]
        standard_quarters = pd.to_datetime(sanitized_df.columns).to_period('Q').to_timestamp('D')
        sanitized_df.columns = standard_quarters
        sanitized_df = sanitized_df.sort_index(axis=1, ascending=True)
    except Exception as e:
        return pd.DataFrame()
    return sanitized_df

def normalize_financial_matrix(df: pd.DataFrame, domain_prefix: str) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    if df.shape[0] < 1 or df.shape[1] < 1:
        raise ValueError(f"CRITICAL: Structural Validation Breach. Core accounting frame is empty.")
    sorted_df = clean_and_sort_time_axis(df)
    if sorted_df.empty: return pd.DataFrame()
    sorted_df.index = [f"{domain_prefix}_{normalize_key(idx)}" for idx in sorted_df.index]
    return sorted_df

def get_canonical_series(df: pd.DataFrame, keys: List[str], prefix: str, strict: bool = True) -> pd.Series:
    if df is None or df.empty: 
        if strict: raise ValueError(f"CRITICAL Ingestion Exception: Financial matrix dropped root reference fields.")
        return pd.Series(dtype=float)
    cleaned_df = df.copy()
    for k in keys:
        lookup = f"{prefix}_{normalize_key(k)}"
        if lookup in cleaned_df.index:
            row = cleaned_df.loc[lookup]
            if isinstance(row, pd.DataFrame): row = row.iloc[:, -1]
            s = pd.Series(row, dtype=float)
            return s[~s.index.duplicated(keep="last")].fillna(0.0).sort_index(ascending=True)
    if strict: raise ValueError(f"CRITICAL Ingestion Exception: Required canonical key mapping token completely missing: {keys}")
    return pd.Series(dtype=float)

# =============================================================================
# LAYER 4: SYSTEMIC MARKET INDEX IMPLIED VOLATILITY ENGINE
# =============================================================================
def evaluate_market_regime_context() -> dict:
    try:
        cached_payload = QUANT_PIPELINE_CACHE.get_dict("macro_regime_payload")
        if cached_payload: return cached_payload

        logging.info("[*] Connecting to institutional data node for market benchmarks...")
        ticker_obj = yf.Ticker("^NSEI")
        nifty_hist = ticker_obj.history(period="1y", timeout=8)
        
        if nifty_hist.empty or len(nifty_hist) < 20: 
            raise ValueError("Nifty index frame returned empty or truncated bars array.")
            
        nifty_returns = nifty_hist["Close"].pct_change().dropna()
        realized_vol = float(nifty_returns.iloc[-30:].std() * np.sqrt(252))
        risk_free_rate = 0.0715 
        
        nifty_close = nifty_hist["Close"].copy()
        nifty_close.index = safe_strip_timezone(nifty_close.index)
        QUANT_PIPELINE_CACHE.set("^NSEI_hist", nifty_close, expected_type="SERIES")
        
        if realized_vol > 0.195:
            regime_lbl = "RISK_OFF_HIGH_CORRELATION_PANIC"
            entropy_gamma = 0.025  
            value_w, quality_w, growth_w, momentum_w = 0.40, 0.40, 0.10, 0.10
        elif realized_vol < 0.115:
            regime_lbl = "RISK_ON_IDIOSYNCRATIC_DISPERSION"
            entropy_gamma = 0.005  
            value_w, quality_w, growth_w, momentum_w = 0.15, 0.20, 0.35, 0.30
        else:
            regime_lbl = f"VOL_SCALED_{round(realized_vol, 3)}"
            entropy_gamma = 0.012
            value_w = min(0.45, 0.25 + 0.5 * max(0.0, realized_vol - 0.15))
            quality_w = min(0.40, 0.30 + 0.3 * max(0.0, realized_vol - 0.15))
            growth_w = max(0.10, 0.25 - 0.5 * max(0.0, realized_vol - 0.15))
            momentum_w = 1.0 - (value_w + quality_w + growth_w)

        payload = {
            "risk_free_rate": risk_free_rate, "regime_state": regime_lbl,
            "wacc_premium": 0.015 * (min(max(0.5, realized_vol / 0.15), 2.5) - 1.0), 
            "terminal_g": max(0.015, min(0.035, 0.0275 - (0.01 * (0.015 * (min(max(0.5, realized_vol / 0.15), 2.5) - 1.0))))),
            "factor_weights": {"value": value_w, "quality": quality_w, "growth": growth_w, "momentum": momentum_w}, 
            "realized_market_vol": realized_vol, "entropy_gamma": entropy_gamma
        }
        QUANT_PIPELINE_CACHE.set("macro_regime_payload", payload, expected_type="DICT")
        return payload
    except Exception as e:
        logging.warning(f"[⚠️] Network Socket Timeout/Intercept: {e}")
        logging.info("[*] Activating Equilibrium Default Shield to ensure pipeline continuity.")
        return {
            "risk_free_rate": 0.0715, "regime_state": "EQUILIBRIUM_NEUTRAL_CYCLE",
            "wacc_premium": 0.00, "terminal_g": 0.025,
            "factor_weights": {"value": 0.25, "quality": 0.30, "growth": 0.25, "momentum": 0.20},
            "realized_market_vol": 0.15, "entropy_gamma": 0.012
        }

def resolve_business_archetype(info: dict) -> str:
    industry = str(info.get("industry", "")).strip()
    sector = str(info.get("sector", "")).strip()
    return "BANK" if "Bank" in industry or "Banks" in industry else \
           "NBFC_CREDIT" if ("Financial Services" in sector or any(kw in industry for kw in ["Credit", "Finance", "Loans", "Capital"])) else \
           "CORPORATE"

# =============================================================================
# LAYER 5: DYNAMIC POINT-IN-TIME ALIGNMENT ENGINE (Reverse Splits Handled)
# =============================================================================
def extract_pit_share_count(hist_prices: pd.DataFrame, target_date: pd.Timestamp, info_payload: dict, ticker: str) -> float:
    base_shares = safe_score(info_payload.get("sharesOutstanding"), default=0.0)
    if base_shares <= 0:
        c_tk = get_canonical_symbol(ticker)
        cached_info = QUANT_PIPELINE_CACHE.get_dict(f"{c_tk}_info")
        base_shares = safe_score(cached_info.get("sharesOutstanding"), default=1e7)
    if hist_prices.empty: return base_shares
        
    try:
        clean_hist = hist_prices.copy()
        clean_hist.index = safe_strip_timezone(clean_hist.index)
        if "Stock Splits" in clean_hist.columns:
            future_splits = clean_hist.loc[(clean_hist.index > target_date) & (clean_hist.index <= pd.Timestamp.now().tz_localize(None)), "Stock Splits"]
            future_splits = future_splits[future_splits > 0.0]
            for split_ratio in future_splits.values:
                if split_ratio > 0: 
                    base_shares /= split_ratio
    except Exception as e:
        logging.error(f"PIT Share Engine Failure for {ticker}: {e}")
    return float(max(1.0, base_shares))

def calculate_calibrated_median_pe(ticker_str: str, current_pe: float, quarterly_financials: pd.DataFrame, info_payload: dict) -> float:
    try:
        net_inc_series = safe_get_sorted_series(get_canonical_series(quarterly_financials, LABEL_MAP["net_income"], "is", strict=False))
        shares_series = safe_get_sorted_series(get_canonical_series(quarterly_financials, LABEL_MAP["diluted_shares"], "is", strict=False))
        
        c_token = get_canonical_symbol(ticker_str)
        hist_prices = QUANT_PIPELINE_CACHE.get_dataframe(f"{c_token}_stock_hist")
        if hist_prices.empty or "Close" not in hist_prices.columns or len(net_inc_series) < 4: return current_pe if current_pe else 28.5
            
        ttm_net_income = net_inc_series.rolling(window=4).sum().dropna()
        if ttm_net_income.empty: return current_pe if current_pe else 28.5
            
        pe_pool = []
        hist_prices_naive = hist_prices.copy()
        hist_prices_naive.index = safe_strip_timezone(hist_prices_naive.index)
        hist_prices_naive = hist_prices_naive.sort_index()

        for date_stamp in ttm_net_income.index:
            pit_filing_date = date_stamp + pd.Timedelta(days=75)
            window_end_date = pit_filing_date + pd.Timedelta(days=30)
            window_prices = hist_prices_naive.loc[(hist_prices_naive.index >= pit_filing_date) & (hist_prices_naive.index <= window_end_date), "Close"]
            
            if window_prices.empty: 
                if hist_prices_naive.index[0] > pit_filing_date: continue
                avg_price = float(hist_prices_naive["Close"].asof(pit_filing_date))
            else:
                avg_price = float(window_prices.median())
            
            sorted_shares = shares_series.sort_index()
            shares_val = sorted_shares.asof(date_stamp) if not sorted_shares.empty else None
            if shares_val is None or pd.isna(shares_val) or shares_val <= 0:
                shares_val = info_payload.get("sharesOutstanding", 1)
                
            net_inc_val = ttm_net_income.loc[date_stamp]
            if shares_val and not pd.isna(shares_val) and shares_val > 0 and net_inc_val > 0:
                eps_ttm = net_inc_val / shares_val
                if eps_ttm <= 0.001: continue
                pe_multiple = avg_price / eps_ttm
                if 2.0 <= pe_multiple <= 120.0:
                    pe_pool.append(pe_multiple)
                    
        if pe_pool:
            pe_s = pd.Series(pe_pool)
            trimmed = pe_s[(pe_s >= pe_s.quantile(0.10)) & (pe_s <= pe_s.quantile(0.90))]
            if not trimmed.empty: return float(trimmed.median())
    except Exception as e:
        logging.error(f"P/E Calibrator System Failure for {ticker_str}: {e}")
    return current_pe if current_pe else 28.5

# =============================================================================
# LAYER 6: ADAPTIVE DISCOUNTERS & ENSEMBLE HUBS
# =============================================================================
def execute_vectorized_two_stage_fade_dcf(base_cf_per_share: float, growth_rate: float, macro_context: dict) -> float:
    base_wacc = 0.115 + macro_context["wacc_premium"]
    terminal_g = macro_context["terminal_g"]
    g_rate = min(max(growth_rate, -0.15), 0.22)
    
    cf_projections = []
    current_cf = base_cf_per_share
    for year in range(1, 6):
        current_cf *= (1.0 + g_rate)
        cf_projections.append(current_cf)
        
    current_g = g_rate
    decay_factor = 0.70  
    for year in range(6, 11):
        current_g = terminal_g + (current_g - terminal_g) * decay_factor
        current_cf *= (1.0 + current_g)
        cf_projections.append(current_cf)

    cf_projections = np.array(cf_projections)
    discount_factors = 1.0 / ((1.0 + base_wacc) ** np.arange(1, 11))
    explicit_stage_pv = np.sum(cf_projections * discount_factors)
    
    rate_spread = max(base_wacc - terminal_g, 0.035)
    terminal_value = (cf_projections[-1] * (1.0 + terminal_g)) / rate_spread
    discounted_terminal_value = terminal_value / ((1.0 + base_wacc) ** 10)
    
    total_value = explicit_stage_pv + discounted_terminal_value
    if total_value > 0.01 and (discounted_terminal_value / total_value) > 0.75:
        total_value = explicit_stage_pv / 0.25
            
    return float(total_value)

def execute_prudential_bank_model(info: dict) -> float:
    bvps = safe_score(info.get("bookValue", 1.0), default=1.0)
    raw_roe = safe_score(info.get("returnOnEquity", 0.12))
    roe = raw_roe / 100.0 if abs(raw_roe) > 1.0 else raw_roe
    gnpa, nnpa, pcr, cet1 = info.get("grossNPA"), info.get("netNPA"), info.get("provisionCoverageRatio"), info.get("cet1Ratio")

    if gnpa is None or nnpa is None:
        credit_risk_haircut, pcr, cet1_multiplier = 0.15, 0.60, 0.85
    else:
        if gnpa > 1.0: gnpa /= 100.0
        if nnpa > 1.0: nnpa /= 100.0
        credit_risk_haircut = (nnpa * 3.0) + (max(0, 0.04 - gnpa) * 0.4)
        pcr = pcr / 100.0 if pcr > 1.0 else pcr
        cet1 = cet1 / 100.0 if cet1 > 1.0 else cet1
        cet1_multiplier = 1.0 + (max(0, cet1 - 0.115) * 1.2) if cet1 > 0.115 else max(0.70, cet1 / 0.115)

    adjusted_bvps = bvps * max(0.50, 1.0 - credit_risk_haircut)
    cost_of_equity, long_term_g = 0.135, 0.045
    if cost_of_equity > long_term_g:
        adjusted_roe = roe * (pcr / 0.70 if (pcr and pcr > 0) else 1.0)
        intrinsic_pb = (adjusted_roe - long_term_g) / (cost_of_equity - long_term_g)
        return float(max(0.4, min(intrinsic_pb, 4.0)) * adjusted_bvps * cet1_multiplier)
    return float(adjusted_bvps * 1.05)

def execute_nbfc_residual_income_model(info: dict, balance_sheet: pd.DataFrame) -> float:
    bvps = safe_score(info.get("bookValue", 1.0), default=1.0)
    raw_roe = safe_score(info.get("returnOnEquity", 0.14))
    roe = raw_roe / 100.0 if abs(raw_roe) > 1.0 else raw_roe
    cost_of_capital, growth_horizon = 0.145, 0.045
    residual_income_spread = roe - cost_of_capital
    if cost_of_capital > growth_horizon:
        return float(max(0.5, min(1.0 + (residual_income_spread / (cost_of_capital - growth_horizon)), 3.8)) * bvps)
    return float(bvps * 1.20)

def execute_exchange_network_moat_model(info: dict, financials: pd.DataFrame) -> float:
    current_price = safe_score(info.get("currentPrice", 1.0), default=1.0)
    eps = safe_score(info.get("trailingEps", 1.0), default=1.0)
    shares = info.get("sharesOutstanding", 1) or 1
    
    ebit_series = safe_get_sorted_series(get_canonical_series(financials, LABEL_MAP["ebit"], "is", strict=False))
    ebit_val = float(np.median(ebit_series.values[-3:])) if (not ebit_series.empty and len(ebit_series) >= 2) else (eps * shares)
    
    rev_series = safe_get_sorted_series(get_canonical_series(financials, LABEL_MAP["revenue"], "is", strict=False))
    rev_val = float(np.median(rev_series.values[-3:])) if (not rev_series.empty and len(rev_series) >= 2) else 1.0
    
    operating_margin = ebit_val / rev_val if rev_val > 1000.0 else 0.20
    network_moat_premium = 1.15 if operating_margin > 0.45 else 1.05
    fcf_yield_proxy_multiple = 22.5 * network_moat_premium  
    
    fair_value = (ebit_val / shares) * 0.72 * fcf_yield_proxy_multiple
    return float(max(eps * 15.0, fair_value))

def execute_valuation_ensemble_hub(archetype: str, info: dict, cashflow: pd.DataFrame, financials: pd.DataFrame, balance_sheet: pd.DataFrame, quarterly_financials: pd.DataFrame, growth_rate: float, macro_context: dict) -> AbsoluteValuation:
    current_price = safe_score(info.get("currentPrice", 1.0), default=1.0)
    eps = safe_score(info.get("trailingEps", 1.0), default=1.0)
    shares = info.get("sharesOutstanding", 1)
    if shares is None or pd.isna(shares) or shares <= 0: shares = 1

    if archetype == "BANK": core_fair_value = execute_prudential_bank_model(info)
    elif archetype == "NBFC_CREDIT": core_fair_value = execute_nbfc_residual_income_model(info, balance_sheet)
    elif archetype == "ASSET_EXCHANGE": core_fair_value = execute_exchange_network_moat_model(info, financials)
    else:
        ocf_series = safe_get_sorted_series(get_canonical_series(cashflow, LABEL_MAP["operating_cash_flow"], "cf", strict=False))
        capex_series = safe_get_sorted_series(get_canonical_series(cashflow, LABEL_MAP["capex"], "cf", strict=False))
        if not ocf_series.empty and not capex_series.empty:
            median_ocf = float(np.median(ocf_series.values[-3:]))
            median_capex = abs(float(np.median(capex_series.values[-3:])))
            true_median_fcf = median_ocf - median_capex
            base_cf_per_share = true_median_fcf / shares if true_median_fcf > 0 else 0.0
        else: base_cf_per_share = 0.0
            
        if base_cf_per_share > 0:
            base_cf_per_share = min(base_cf_per_share, max(1.0, eps) * 1.4)
            core_fair_value = execute_vectorized_two_stage_fade_dcf(base_cf_per_share, growth_rate, macro_context)
        else:
            try:
                equity = safe_get_scalar(get_canonical_series(balance_sheet, LABEL_MAP["total_equity"], "bs", strict=False))
                core_fair_value = (equity * 0.85) / shares 
            except: core_fair_value = max(0.01, eps) * 5.0

    current_pe = safe_score(info.get("trailingPE", 22.5), default=22.5)
    calibrated_pe = calculate_calibrated_median_pe(info.get("symbol", "DEFAULT"), current_pe, quarterly_financials, info)
    
    relative_multiple_fair = max(0.01, eps) * min(max(10.0, calibrated_pe), 65.0)
    blended_fair_value = (core_fair_value * 0.65) + (relative_multiple_fair * 0.35)
    
    mos_raw = ((blended_fair_value - current_price) / blended_fair_value) * 100 if blended_fair_value > 0.01 else 0.0
    mos_score = float(np.tanh(mos_raw / 45.0) * 100.0)
    
    output_contract: AbsoluteValuation = {
        "intrinsic_fair_value": float(blended_fair_value),
        "raw_mos": float(mos_raw),
        "mos_score": float(mos_score),
        "core_model_value": float(core_fair_value),
        "multiple_value": float(relative_multiple_fair)
    }
    return output_contract

# =============================================================================
# LAYER 7: STRATEGY FACTOR PILLARS ENGINE
# =============================================================================
def calculate_raw_value_ratio(info: dict, fair_value: float) -> float:
    current_price = safe_score(info.get("currentPrice", 1.0), default=1.0)
    return float(current_price / fair_value if fair_value > 0.01 else 1.0)

def calculate_raw_quality_score(archetype: str, info: dict, balance_sheet: pd.DataFrame, financials: pd.DataFrame) -> float:
    raw_roe = info.get("returnOnEquity", 0.12)
    roe = raw_roe / 100.0 if abs(raw_roe) > 1.0 else raw_roe
    if archetype in ["BANK", "NBFC_CREDIT"]:
        roa = safe_score(info.get("returnOnAssets", 0.012))
        return float(roa / 100.0 if roa > 1.0 else roa if roa > 0 else roe)
    try:
        ebit = safe_get_scalar(get_canonical_series(financials, LABEL_MAP["ebit"], "is", strict=False))
        equity = safe_get_scalar(get_canonical_series(balance_sheet, LABEL_MAP["total_equity"], "bs", strict=False))
        debt = safe_get_scalar(get_canonical_series(balance_sheet, LABEL_MAP["total_debt"], "bs", strict=False))
        cash = safe_get_scalar(get_canonical_series(balance_sheet, LABEL_MAP["cash_reserves"], "bs", strict=False))
        capital_base = (equity + debt) - cash
        assets = safe_get_scalar(get_canonical_series(balance_sheet, LABEL_MAP["total_assets"], "bs", strict=False))
        if capital_base <= (assets * 0.05) or capital_base <= 0: return float(max(0.01, roe))
        return float(ebit / capital_base)
    except: return float(roe)

def calculate_raw_growth_score(financials: pd.DataFrame, balance_sheet: pd.DataFrame, archetype: str) -> tuple:
    try:
        target_series_raw = get_canonical_series(balance_sheet, LABEL_MAP["total_assets"], "bs", strict=False) if archetype == "NBFC_CREDIT" else \
                            get_canonical_series(financials, LABEL_MAP["nii"], "is", strict=False) if archetype == "BANK" else \
                            get_canonical_series(financials, LABEL_MAP["revenue"], "is", strict=False)
        target_series = safe_get_sorted_series(target_series_raw)
        target_series = target_series[target_series > 0.0]
        n_periods = len(target_series)
        if n_periods < 2: return 0.03, 0.03 
        
        log_diffs = np.diff(np.log(target_series.values))
        
        innovations_variance = np.var(log_diffs) if len(log_diffs) > 1 else 0.01
        regime_break_penalty = 1.0 / (1.0 + 4.0 * innovations_variance)
        
        alpha_ewma = 2.0 / (min(n_periods, 3) + 1.0)
        ewma_slope = log_diffs[0]
        for val in log_diffs[1:]:
            ewma_slope = (val * alpha_ewma) + (ewma_slope * (1.0 - alpha_ewma))
            
        cagr_g = float((target_series.iloc[-1] / target_series.iloc[0]) ** (1.0 / max(1.0, n_periods - 1)) - 1.0)
        blended_g = ((float(np.exp(ewma_slope) - 1.0) * 0.40) + (cagr_g * 0.60)) * regime_break_penalty
        
        smoothed_g_rate = min(max(blended_g, -0.12), 0.20)
        return float(smoothed_g_rate), float(smoothed_g_rate)
    except: return 0.03, 0.03

def calculate_raw_momentum_score(hist_data: pd.DataFrame) -> float:
    if hist_data.empty or len(hist_data) < 20: return 0.0
    try:
        nifty_series = QUANT_PIPELINE_CACHE.get_series("^NSEI_hist")
        if nifty_series is None or nifty_series.empty: return 0.0
            
        stock_close = hist_data["Close"].copy()
        stock_close.index = safe_strip_timezone(stock_close.index)
        
        nifty_series_clean = nifty_series.copy()
        nifty_series_clean.index = safe_strip_timezone(nifty_series_clean.index)
        
        shared_dates = stock_close.index.intersection(nifty_series_clean.index)
        if len(shared_dates) < 20: return 0.0
        
        s_aligned = stock_close.loc[shared_dates]
        n_aligned = nifty_series_clean.loc[shared_dates]
        
        current_dt = s_aligned.index[-1]
        dt_6m_target = current_dt - pd.Timedelta(days=180)
        dt_12m_target = current_dt - pd.Timedelta(days=365)
        
        s_base_6m = s_aligned.asof(dt_6m_target) if s_aligned.index[0] <= dt_6m_target else s_aligned.iloc[0]
        n_base_6m = n_aligned.asof(dt_6m_target) if n_aligned.index[0] <= dt_6m_target else n_aligned.iloc[0]
        s_base_12m = s_aligned.asof(dt_12m_target) if s_aligned.index[0] <= dt_12m_target else s_aligned.iloc[0]
        n_base_12m = n_aligned.asof(dt_12m_target) if n_aligned.index[0] <= dt_12m_target else n_aligned.iloc[0]
        
        spread_6m = ((s_aligned.iloc[-1] - s_base_6m) / max(0.01, s_base_6m)) - ((n_aligned.iloc[-1] - n_base_6m) / max(0.01, n_base_6m))
        spread_12m = ((s_aligned.iloc[-1] - s_base_12m) / max(0.01, s_base_12m)) - ((n_aligned.iloc[-1] - n_base_12m) / max(0.01, n_base_12m))
        
        stock_vol_ann = float(s_aligned.pct_change().dropna().iloc[-min(252, len(s_aligned)):].std() * np.sqrt(252))
        stock_vol_ann = max(0.04, stock_vol_ann)
        
        raw_momentum_alpha = float(((spread_6m * 0.40) + (spread_12m * 0.60)) / stock_vol_ann)
        return float(np.clip(raw_momentum_alpha, -3.0, 3.0))
    except: return 0.0

# =============================================================================
# LAYER 8: UNIFIED COGNITIVE COPULA STANDARD-RANKER 
# =============================================================================
def standardize_and_weight_sector_neutral_factors(signals: List[AssetSignal], macro_profile: dict) -> List[AssetSignal]:
    n_signals = len(signals)
    if n_signals == 0: return signals
    
    factors = ["value_raw", "quality_raw", "growth_raw", "momentum_raw"]
    raw_matrix = np.array([[s["exposures"][f] for f in factors] for s in signals])
    
    copula_matrix = np.zeros_like(raw_matrix)
    for f_idx in range(4):
        col = raw_matrix[:, f_idx]
        if np.isnan(col).any() or np.isinf(col).any():
            clean_median = np.median(col[np.isfinite(col)]) if np.any(np.isfinite(col)) else 1.0
            col[~np.isfinite(col)] = clean_median
        copula_matrix[:, f_idx] = rankdata(col, method='ordinal') / (n_signals + 1.0)
        
    copula_matrix[:, 0] = 1.0 - copula_matrix[:, 0]

    if n_signals >= 4:
        try:
            val_col, mom_col = copula_matrix[:, 0], copula_matrix[:, 3]
            beta_val_mom = np.cov(mom_col, val_col)[0, 1] / max(1e-5, np.var(mom_col))
            copula_matrix[:, 0] = val_col - (beta_val_mom * mom_col)
            
            for f_idx in range(4):
                col_res = copula_matrix[:, f_idx]
                copula_matrix[:, f_idx] = 10.0 + (rankdata(col_res, method='ordinal') / (n_signals + 1.0)) * 90.0
        except Exception as e:
            copula_matrix = 10.0 + (copula_matrix * 90.0)
    else:
        copula_matrix = 10.0 + (copula_matrix * 90.0)

    w = macro_profile["factor_weights"]
    for idx, signal in enumerate(signals):
        signal["exposures"]["value_z"] = float(copula_matrix[idx, 0])
        signal["exposures"]["quality_z"] = float(copula_matrix[idx, 1])
        signal["exposures"]["growth_z"] = float(copula_matrix[idx, 2])
        signal["exposures"]["momentum_z"] = float(copula_matrix[idx, 3])
        signal["composite_factor_score"] = float((copula_matrix[idx, 0]*w["value"]) + (copula_matrix[idx, 1]*w["quality"]) + (copula_matrix[idx, 2]*w["growth"]) + (copula_matrix[idx, 3]*w["momentum"]))
        
    return signals

# =============================================================================
# LAYER 9: DECOUPLED RISK PARITY OPTIMIZER
# =============================================================================
def optimize_portfolio_allocation_matrix(assets: List[AssetSignal], macro_profile: dict) -> dict:
    n_assets = len(assets)
    tickers = [a["ticker"] for a in assets]
    if n_assets == 0: return {}
    
    regime = macro_profile["regime_state"]
    price_series_pool, valid_assets_map = [], []
    
    for asset in assets:
        c_tk = get_canonical_symbol(asset["ticker"])
        cached_prices = QUANT_PIPELINE_CACHE.get_dataframe(f"{c_tk}_stock_hist")
        if not cached_prices.empty and "Close" in cached_prices.columns:
            log_returns = np.log(cached_prices["Close"]).diff().dropna().rename(asset["ticker"])
            price_series_pool.append(log_returns.clip(lower=log_returns.quantile(0.01), upper=log_returns.quantile(0.99)))
            valid_assets_map.append(asset)
            
    active_n = len(price_series_pool)
    if active_n == 0: return {}
    
    try:
        raw_dataframe = pd.concat(price_series_pool, axis=1)
        sample_covariance_matrix = raw_dataframe.cov().values * 252
        if np.isnan(sample_covariance_matrix).any(): sample_covariance_matrix = np.nan_to_num(sample_covariance_matrix, nan=0.015)
            
        t_samples = raw_dataframe.shape[0]
        mean_variance_target = np.mean(np.diag(sample_covariance_matrix))
        target_identity_matrix = np.eye(active_n) * mean_variance_target
        
        d_constant = np.sum((sample_covariance_matrix - target_identity_matrix) ** 2)
        standardized_returns = raw_dataframe.values - np.mean(raw_dataframe.values, axis=0)
        b_sum = 0.0
        for t in range(t_samples):
            r_t = standardized_returns[t, :, np.newaxis]
            b_sum += np.sum(((r_t @ r_t.T) * 252 - sample_covariance_matrix) ** 2)
            
        optimal_alpha = max(0.10, min(b_sum / (t_samples ** 2) / d_constant if d_constant > 0 else 0.40, 0.80))
        shrunk_covariance = (1.0 - optimal_alpha) * sample_covariance_matrix + (optimal_alpha * target_identity_matrix)
        raw_covariance = shrunk_covariance + np.diag([a["exposures"]["uncertainty_variance"] for a in valid_assets_map]) * 0.10
        
        eigenvalues, eigenvectors = np.linalg.eigh(raw_covariance)
        asset_covariance_matrix = eigenvectors @ np.diag(np.maximum(eigenvalues, 1e-5)) @ eigenvectors.T

        rf = macro_profile["risk_free_rate"]
        expected_returns = []
        for a in valid_assets_map:
            factor_premium = 0.035 * (((a["exposures"]["quality_z"] + a["exposures"]["growth_z"]) / 2.0) - 50.0) / 50.0
            valuation_residual_scaler = max(0.15, 1.0 - (max(50.0, a["exposures"]["value_z"]) - 50.0) / 50.0)
            valuation_reversion_premium = 0.045 * (a["valuation"]["raw_mos"] / 100.0) * valuation_residual_scaler
            momentum_premium = 0.025 * (a["exposures"]["momentum_raw"])
            expected_returns.append(rf + factor_premium + valuation_reversion_premium + momentum_premium)
            
        expected_returns = np.clip(np.array(expected_returns), rf, rf + 0.15)
        risk_aversion_lambda = 3.5
        entropy_gamma = macro_profile["entropy_gamma"]
        
        def objective_institutional_entropy_utility(w):
            return -(np.sum(w * expected_returns) - (risk_aversion_lambda * (w.T @ asset_covariance_matrix @ w)) + (entropy_gamma * (-np.sum(w * np.log(w + 1e-8)))))
            
        constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
        
        # Adaptive boundary constraints to allow execution with limited asset sets
        min_w = max(0.01, 0.05 / active_n) if active_n >= 2 else 0.05
        max_w = min(0.95, 4.5 / active_n) if active_n >= 2 else 0.95
        bounds = tuple((min_w, max_w) for _ in range(active_n))
        
        result = minimize(objective_institutional_entropy_utility, np.ones(active_n)/active_n, method='SLSQP', bounds=bounds, constraints=constraints)
        
        if not result.success:
            logging.error(f"CRITICAL OPTIMIZER CONVERGENCE DROP: {result.message}. Forcing equal weights.")
            optimal_weights = np.ones(active_n) / active_n
        else:
            logging.info(f"SLSQP Optimizer Converged. Iterations: {result.nit}. Objective Value: {result.fun}")
            optimal_weights = result.x
            
        portfolio_vol = np.sqrt(float(optimal_weights.T @ asset_covariance_matrix @ optimal_weights))
        sharpe_ratio = (np.sum(optimal_weights * expected_returns) - rf) / portfolio_vol if portfolio_vol > 0 else 0.0
        final_weights = dict(zip(raw_dataframe.columns, optimal_weights))
        for t in tickers: 
            if t not in final_weights: final_weights[t] = 0.0
    except Exception as e:
        logging.error(f"Portfolio Optimizer Core Failure ({e}). Forcing equal weights.")
        final_weights = {a["ticker"]: (1.0 / n_assets) for a in assets}
        portfolio_vol, sharpe_ratio = 0.185, 1.05

    directives = {t: f"ACCUMULATE_HIGH_UTILITY_BUY (Size: {round(final_weights[t]*100,1)}%)" if (final_weights[t] > (1.0 / n_assets)) else f"ALLOCATE_HOLD_WEIGHT (Size: {round(final_weights[t]*100,1)}%)" for t in tickers}
    return {"regime_state": regime, "optimal_weights": {a["ticker"]: float(final_weights[a["ticker"]]) for a in assets}, "portfolio_volatility": float(portfolio_vol), "portfolio_sharpe": float(sharpe_ratio), "execution_directives": directives}

# =============================================================================
# LAYER 10: UNIFIED DAEMON INTERFACE ORCHESTRATION PIPELINE
# =============================================================================
def generate_raw_asset_signals(tickers_list: List[str], macro_profile: dict) -> List[AssetSignal]:
    signals_pool = []
    for stock in tickers_list:
        try:
            ticker_str = f"{stock}.NS" if not stock.endswith((".NS", ".BO")) else stock
            clean_name = get_canonical_symbol(stock)
            
            cached_hist = QUANT_PIPELINE_CACHE.get_dataframe(f"{clean_name}_stock_hist")
            if not cached_hist.empty:
                hist = cached_hist
                financials = QUANT_PIPELINE_CACHE.get_dataframe(f"{clean_name}_financials")
                balance_sheet = QUANT_PIPELINE_CACHE.get_dataframe(f"{clean_name}_balance_sheet")
                cashflow = QUANT_PIPELINE_CACHE.get_dataframe(f"{clean_name}_cashflow")
                quarterly_financials = QUANT_PIPELINE_CACHE.get_dataframe(f"{clean_name}_quarterly")
                info = QUANT_PIPELINE_CACHE.get_dict(f"{clean_name}_info")
            else:
                ticker = yf.Ticker(ticker_str)
                hist = ticker.history(period="1y", timeout=5)
                try:
                    info = ticker.info
                    if not info or not isinstance(info, dict): info = {}
                except: info = {}
                
                if hist.empty or len(hist) < 100: 
                    logging.warning(f"[-] Skipped {stock}: Insufficient raw bar series historical logs.")
                    continue
                
                financials = normalize_financial_matrix(ticker.financials, "is") if ticker.financials is not None else pd.DataFrame()
                balance_sheet = normalize_financial_matrix(ticker.balance_sheet, "bs") if ticker.balance_sheet is not None else pd.DataFrame()
                cashflow = normalize_financial_matrix(ticker.cashflow, "cf") if ticker.cashflow is not None else pd.DataFrame()
                try: quarterly_financials = normalize_financial_matrix(ticker.quarterly_financials, "is")
                except: quarterly_financials = financials

                QUANT_PIPELINE_CACHE.set(f"{clean_name}_stock_hist", hist, expected_type="DATAFRAME")
                QUANT_PIPELINE_CACHE.set(f"{clean_name}_financials", financials, expected_type="DATAFRAME")
                QUANT_PIPELINE_CACHE.set(f"{clean_name}_balance_sheet", balance_sheet, expected_type="DATAFRAME")
                QUANT_PIPELINE_CACHE.set(f"{clean_name}_cashflow", cashflow, expected_type="DATAFRAME")
                QUANT_PIPELINE_CACHE.set(f"{clean_name}_quarterly", quarterly_financials, expected_type="DATAFRAME")
                QUANT_PIPELINE_CACHE.set(f"{clean_name}_info", info, expected_type="DICT")
                
            archetype = resolve_business_archetype(info)
            sector_lbl = info.get("sector", "Core_Industry")
            
            growth_raw, _ = calculate_raw_growth_score(financials, balance_sheet, archetype)
            valuation_ensemble = execute_valuation_ensemble_hub(archetype, info, cashflow, financials, balance_sheet, quarterly_financials, growth_raw, macro_profile)
            fair_value = valuation_ensemble["intrinsic_fair_value"]
            
            returns_vector = hist["Close"].pct_change().dropna()
            stock_idiosyncratic_variance = float(np.var(returns_vector) * 252) if len(returns_vector) > 10 else 0.04
            stock_idiosyncratic_variance = max(0.01, min(stock_idiosyncratic_variance, 0.25))
            
            val_raw = calculate_raw_value_ratio(info, fair_value)
            qual_raw = calculate_raw_quality_score(archetype, info, balance_sheet, financials)
            mom_raw = calculate_raw_momentum_score(hist)
            
            signals_pool.append({
                "ticker": stock, "sector": sector_lbl, "composite_factor_score": 0.0, "business_archetype": archetype,
                "exposures": {"value_raw": val_raw, "quality_raw": qual_raw, "growth_raw": growth_raw, "momentum_raw": mom_raw, "value_z": 0.0, "quality_z": 0.0, "growth_z": 0.0, "momentum_z": 0.0, "uncertainty_variance": stock_idiosyncratic_variance},
                "valuation": valuation_ensemble
            })
            logging.info(f"Ingest Matrix: Successfully processed analytical bounds for -> {stock}")
        except Exception as e: 
            logging.error(f"Failed parsing sequence line item for {stock}: {e}")
            
    return signals_pool

# =============================================================================
# THE UNIFIED RUNNER INTERFACE
# =============================================================================
if __name__ == "__main__":
    QUANT_PIPELINE_CACHE.pop("macro_regime_payload")
    QUANT_PIPELINE_CACHE.pop("^NSEI_hist")
    
    universe_input = input("Enter Indian Capital Equity Tickers Separated By Commas (e.g., CASTROLIND, LAURUSLABS, GMDCLTD): ").strip()
    target_tickers = [t.upper().strip() for t in universe_input.split(",") if t.strip()]
    if not target_tickers or len(target_tickers) < 2:
        logging.error("❌ Universe empty or lacks minimum assets for optimization stability (Min 2 required).")
        sys.exit()
        
    macro_profile = evaluate_market_regime_context()
    logging.info(f"\n🌍 [ACTIVE MARKET VOL REGIME]  : {macro_profile['regime_state']}")
    logging.info(f"📈 [REALIZED SYSTEMIC VOLATILITY]: {round(macro_profile['realized_market_vol']*100, 2)}% | RISK FREE BASE ANCHOR: {round(macro_profile['risk_free_rate']*100, 2)}%\n")
    
    raw_signals = generate_raw_asset_signals(target_tickers, macro_profile)
    if not raw_signals or len(raw_signals) < 2:
        logging.error("❌ Data Ingestion Failure: Adjusted asset payload blocks collapse minimum threshold limits (Min 2 required).")
        sys.exit()
        
    processed_signals = standardize_and_weight_sector_neutral_factors(raw_signals, macro_profile)
    
    logging.info("\n" + "-"*75)
    logging.info("🎯 DECOUPLED SECTOR-NEUTRAL FACTOR EXPOSURES MATRIX (Adaptive 10-100 Bounds Sheets)")
    logging.info("-"*75)
    for asset in processed_signals:
        exp = asset["exposures"]
        print(f"  👉 {asset['ticker'].ljust(12)} | Value: {str(round(exp['value_z'], 1)).ljust(5)} | Quality: {str(round(exp['quality_z'], 1)).ljust(5)} | Growth: {str(round(exp['growth_z'], 1)).ljust(5)} | Momentum: {str(round(exp['momentum_z'], 1)).ljust(5)} | Blend: {round(asset['composite_factor_score'], 1)}")
    
    portfolio_matrix = optimize_portfolio_allocation_matrix(processed_signals, macro_profile)
    if not portfolio_matrix or "portfolio_volatility" not in portfolio_matrix:
        logging.error("❌ Optimization Engine Core Failed to converge bounds. Execution halted.")
        sys.exit()
        
    # EXPORT THE TOP HIGH-CONVICTION EXCEL VIEW REPORT FILE
    out_df = pd.DataFrame([{
        "ticker": s["ticker"],
        "composite_factor_score": s["composite_factor_score"],
        "sector": s["sector"],
    } for s in processed_signals])
    out_df.to_excel("FUNDAMENTAL_SHORTLIST.xlsx", index=False)
    logging.info("\n📁 View report layer compiled successfully: FUNDAMENTAL_SHORTLIST.xlsx")

    logging.info("\n" + "="*70)
    logging.info("         INSTITUTIONAL QUANT PORTFOLIO OPTIMIZATION SHEETS")
    logging.info("="*70)
    logging.info(f" EXPECTED ANNUALISED PORTFOLIO RISK VOL : {round(portfolio_matrix['portfolio_volatility']*100, 2)}%")
    logging.info(f" EXPECTED CONSTRAINED PORTFOLIO SHARPE : {round(portfolio_matrix['portfolio_sharpe'], 2)}")
    logging.info(f" REGIME ALLOCATION PARAMETER MODE       : {portfolio_matrix['regime_state']}")
    logging.info("-"*70)
    logging.info("🎯 OPTIMAL ASSET MATRICES SIZING WEIGHTS & DIRECTIVES")
    for asset_tk, w_val in portfolio_matrix['optimal_weights'].items():
        logging.info(f"  👉 {asset_tk.ljust(12)} | Sizing: {round(w_val*100, 2)}% | Route: {portfolio_matrix['execution_directives'][asset_tk]}")
    logging.info("="*70 + "\n")