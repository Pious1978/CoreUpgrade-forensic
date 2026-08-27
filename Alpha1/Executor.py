import pandas as pd
import numpy as np
import yfinance as yf
import warnings
import os
import time

warnings.filterwarnings("ignore")

PORTFOLIO_PATH = r"C:\Users\GS102\OneDrive\Research\Invest\Stocks_Holdings_Statement.xlsx"
NIFTY_SYMBOL = "^NSEI"

# --- CANONICAL SECTOR TAXONOMY MAP ---
SECTOR_NORMALIZATION_MAP = {
    "INFORMATION TECHNOLOGY": ["IT", "TECH", "SOFTWARE", "IT SERVICES", "INFORMATION TECHNOLOGY", "DIGITAL"],
    "FINANCIAL SERVICES": ["BANK", "BANKS", "NBFC", "FINANCIAL", "FINANCE", "FINANCIAL SERVICES", "INSURANCE"],
    "HEALTHCARE": ["PHARMA", "PHARMACEUTICALS", "HEALTHCARE", "HOSPITALS", "LABS", "LAURUSLABS", "BIOTECH"],
    "METALS AND MINING": ["STEEL", "METALS", "MINING", "IRON", "ALUMINIUM", "COPPER", "HINDALCO", "JSWSTEEL"],
    "CONSUMER CYCLICAL": ["RETAIL", "AUTOMOBILE", "AUTO", "TEXTILES", "TRENT", "DIXON"]
}

def normalize_sector(raw_sector):
    raw_upper = str(raw_sector).upper().strip()
    for canonical_name, aliases in SECTOR_NORMALIZATION_MAP.items():
        if any(alias in raw_upper for alias in aliases):
            return canonical_name
    return "OTHER"


class AlphaV26MasterEngine:
    def __init__(self, symbol, portfolio_path=PORTFOLIO_PATH, total_capital=1000000.0, max_drawdown_limit=0.10):
        self.symbol = symbol.upper().strip()
        self.raw_symbol = self.symbol.replace(".NS", "").replace(".BO", "")
        self.portfolio_path = portfolio_path
        self.total_capital = total_capital
        self.max_drawdown_limit = max_drawdown_limit
        
        if not (self.symbol.endswith(".NS") or self.symbol.endswith(".BO")):
            self.symbol += ".NS"
            
        self.ticker_obj = yf.Ticker(self.symbol)
        self._cached_info = None
        self.df = None
        self.market_df = None
        self.portfolio_df = None
        
        # --- Standardized Continuous Space State Matrix Vectors ---
        self.vectors = {
            "Trend_ZScore": np.nan,
            "Volume_Sponsorship_Pct": np.nan,
            "Compression_Pct": np.nan,
            "Timing_Percentile": np.nan,
            "Continuous_Regime_Score": np.nan,
            "Quality_Stability": np.nan,
            "Liquidity_Velocity": np.nan,
            "Liquidity_Depth": np.nan,
            "Joint_Failure_Risk": np.nan,
            "RiskReward": np.nan
        }
        
        # --- Hierarchical Tiered Veto Mapping Matrix ---
        self.vetoes = {
            "FATAL": [],
            "STRUCTURAL": [],
            "TACTICAL": []
        }
        self.logs = []

    def _fetch_yf_history(self, ticker_obj, period_str="2y"):
        for attempt in range(3):
            try:
                feed = ticker_obj.history(period=period_str)
                if feed is not None and not feed.empty:
                    return feed
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        return None

    @property
    def info(self):
        if self._cached_info is None:
            for attempt in range(3):
                try:
                    self._cached_info = self.ticker_obj.info
                    if isinstance(self._cached_info, dict) and self._cached_info:
                        break
                except Exception:
                    time.sleep(1.0 * (attempt + 1))
            if not isinstance(self._cached_info, dict) or not self._cached_info:
                self._cached_info = {}
        return self._cached_info

    # =========================================================================
    # 1. DATA PIPELINE LAYER (TEMPORAL SYNC & COMPLETENESS CONTRACT)
    # =========================================================================
    def load_data_pipeline(self):
        """Loads dataset and verifies historical completeness constraints"""
        asset_feed = self._fetch_yf_history(self.ticker_obj, "2y")
        if asset_feed is None:
            return False
        if isinstance(asset_feed.columns, pd.MultiIndex):
            asset_feed.columns = asset_feed.columns.get_level_values(0)
        self.df = asset_feed.dropna(subset=["Open", "High", "Low", "Close"])

        # Hard Data Completeness Contract Gate
        if len(self.df) < 200:
            self.vetoes["FATAL"].append("VETO_DATA_COMPLETENESS_VIOLATION")
            self.logs.append(f"[DATA] Incomplete timeline array history ({len(self.df)} bars). Asset processing rejected.")
            return False

        mkt_feed = self._fetch_yf_history(yf.Ticker(NIFTY_SYMBOL), "2y")
        if mkt_feed is None or len(mkt_feed) < 200:
            return False
        if isinstance(mkt_feed.columns, pd.MultiIndex):
            mkt_feed.columns = mkt_feed.columns.get_level_values(0)
        self.market_df = mkt_feed.dropna(subset=["Open", "High", "Low", "Close"])

        # Temporal Sync Check
        last_asset_date = pd.to_datetime(self.df.index[-1])
        last_mkt_date = pd.to_datetime(self.market_df.index[-1])
        days_delta = abs((last_asset_date - last_mkt_date).days)
        if days_delta > 4:
            self.vetoes["FATAL"].append("VETO_TEMPORAL_DESYNCHRONIZATION")
            self.logs.append(f"[DATA] High calendar mismatch found: {days_delta} days delta. Pipeline locked.")

        if os.path.exists(self.portfolio_path):
            try:
                self.portfolio_df = pd.read_excel(self.portfolio_path)
                self.portfolio_df.columns = [c.strip() for c in self.portfolio_df.columns]
            except Exception:
                self.portfolio_df = pd.DataFrame()
        else:
            self.portfolio_df = pd.DataFrame()
            
        return True

    # =========================================================================
    # 2. ADAPTIVE STATE VECTOR ENGINE
    # =========================================================================
    def calculate_adaptive_state_vectors(self):
        """Extracts relative attributes and computes volatility expected move coordinates"""
        close = self.df["Close"]
        high = self.df["High"]
        low = self.df["Low"]
        vol = self.df["Volume"]
        
        self.c_price = close.iloc[-1]
        self.c_high = high.iloc[-1]
        self.c_low = low.iloc[-1]
        self.c_close = close.iloc[-1]
        
        self.atr_series = ((high - low) / close).dropna()
        atr_calc = (high - low).rolling(20).mean().dropna()
        self.c_atr_20 = float(atr_calc.iloc[-1]) if not atr_calc.empty else 0.0
        
        raw_rvol_series = (vol / vol.rolling(20).mean().clip(lower=1e-6)).dropna()
        if len(raw_rvol_series) >= 20:
            self.vectors["Volume_Sponsorship_Pct"] = float(raw_rvol_series.tail(252).rank(pct=True).iloc[-1] * 100.0)
            
        if len(self.atr_series) >= 20:
            self.vectors["Compression_Pct"] = float((1.0 - self.atr_series.tail(252).rank(pct=True).iloc[-1]) * 100.0)

        rolling_mean_200 = close.rolling(200).mean().dropna()
        rolling_std_200 = close.rolling(200).std().dropna()
        if not rolling_mean_200.empty and not rolling_std_200.empty:
            current_z_score = (self.c_price - rolling_mean_200.iloc[-1]) / max(rolling_std_200.iloc[-1], 1e-6)
            self.vectors["Trend_ZScore"] = float(max(0.0, min((current_z_score + 2.0) / 4.0 * 100.0, 100.0)))

        # ATR Expected Move Modeling
        if self.c_atr_20 > 0:
            self.sl_price = round(self.c_price - (1.5 * self.c_atr_20), 2)
            self.target_price = round(self.c_price + (3.0 * self.c_atr_20), 2)
        else:
            self.sl_price = round(self.c_price * 0.95, 2)
            self.target_price = round(self.c_price * 1.15, 2)
            
        self.risk_distance = self.c_price - self.sl_price
        self.reward_distance = self.target_price - self.c_price
        self.raw_rr = self.reward_distance / max(self.risk_distance, 1e-6)
        
        # Nonlinear Asymmetric Soft-Clipping Risk-Reward Engine
        self.vectors["RiskReward"] = float(np.tanh(self.raw_rr / 2.0) * 100.0)

        # Volatility-Normalized Timing Matrix
        target_trigger_zone = self.c_price + (0.5 * self.c_atr_20)
        dist_to_trigger_pct = abs((target_trigger_zone - self.c_price) / self.c_price) * 100
        atr_normalizer = max(self.c_atr_20 * 100, 1e-6)
        self.vectors["Timing_Percentile"] = float(max(0.0, min(100.0 * (1.0 - (dist_to_trigger_pct / atr_normalizer)), 100.0)))

        # Polyfit Regression Asset-to-Index Beta
        try:
            aligned_returns = pd.concat([close.pct_change(), self.market_df["Close"].pct_change()], axis=1, join="inner").dropna()
            if len(aligned_returns) >= 60:
                asset_ret = np.clip(aligned_returns.iloc[:, 0].tail(90).values, -0.06, 0.06)
                market_ret = np.clip(aligned_returns.iloc[:, 1].tail(90).values, -0.04, 0.04)
                self.asset_beta = np.polyfit(market_ret, asset_ret, 1)[0] if np.var(market_ret) > 1e-8 else 1.0
            else:
                self.asset_beta = 1.0
        except Exception:
            self.asset_beta = 1.0
            
        return True

    # =========================================================================
    # 3. SIGNAL LAYER (CONTINUOUS COHORT REGIME STABILITY)
    # =========================================================================
    def compute_continuous_regime_vector(self):
        """Calculates index volatility clustering metrics across standard profiles"""
        m_close = self.market_df["Close"]
        m_high = self.market_df["High"]
        m_low = self.market_df["Low"]
        
        m_ema200 = m_close.rolling(window=200).mean()
        m_returns = m_close.pct_change()
        asset_returns = self.df["Close"].pct_change()
        
        vol_rolling_short = m_returns.rolling(10).std()
        vol_rolling_long = m_returns.rolling(50).std()
        vol_clustering_ratio = vol_rolling_short / vol_rolling_long.clip(lower=1e-6)
        
        aligned = pd.concat([asset_returns, m_returns], axis=1, join="inner").dropna()
        aligned.columns = ["Asset", "Market"]
        
        if len(aligned) > 90:
            rolling_correlation_series = aligned["Asset"].rolling(90).corr(aligned["Market"]).dropna()
            if not rolling_correlation_series.empty:
                correlation_pct = float((1.0 - rolling_correlation_series.tail(252).rank(pct=True).iloc[-1]) * 100.0)
            else:
                correlation_pct = 50.0
        else:
            correlation_pct = 50.0

        trend_coordinate = float((m_close - m_ema200).tail(252).rank(pct=True).iloc[-1] * 100.0)
        vol_clustering_pct = float((1.0 - vol_clustering_ratio.tail(252).rank(pct=True).iloc[-1]) * 100.0)
        
        raw_coordinate = (trend_coordinate * 0.40) + (vol_clustering_pct * 0.30) + (correlation_pct * 0.30)
        
        if m_close.iloc[-1] < m_ema200.iloc[-1]:
            self.vectors["Continuous_Regime_Score"] = float(max(0.0, min(raw_coordinate * 0.65, 100.0)))
        else:
            self.vectors["Continuous_Regime_Score"] = float(max(0.0, min(raw_coordinate, 100.0)))

    # =========================================================================
    # 4. RISK LAYER (NON-LINEAR ADAPTIVE FAILURE SURFACES)
    # =========================================================================
    def calculate_resilient_quality_liquidity(self):
        """Grades multi-quarter structural fundamentals and processes trading depth metrics"""
        close = self.df["Close"]
        vol = self.df["Volume"]
        high = self.df["High"]
        low = self.df["Low"]
        
        try:
            q_financials = self.ticker_obj.quarterly_financials
            stability_score = 50.0
            if q_financials is not None and not q_financials.empty:
                net_income_rows = [r for r in q_financials.index if "Net Income" in str(r)]
                if net_income_rows:
                    net_income_series = q_financials.loc[net_income_rows[0]].dropna()
                    if len(net_income_series) >= 3:
                        stability_score = 100.0 * (1.0 - min(net_income_series.std() / abs(net_income_series.mean()), 1.0))
        except Exception:
            stability_score = 50.0

        roe = self.info.get("returnOnEquity", 0.12) if self.info else 0.12
        roe = roe * 100.0 if roe < 1.0 else roe
        self.vectors["Quality_Stability"] = float(max(0.0, min((stability_score * 0.4) + (roe * 2.5), 100.0)))
        
        # Clean Fallback Routing for uncomputable volume velocity profiles
        denom = vol.rolling(20).mean().clip(lower=1e-6)
        raw_vol_velocity_series = ((vol - vol.shift(1)).rolling(20).std() / denom).dropna()
        if not raw_vol_velocity_series.empty:
            self.vectors["Liquidity_Velocity"] = float(raw_vol_velocity_series.tail(252).rank(pct=True).iloc[-1] * 100.0)
        else:
            self.vectors["Liquidity_Velocity"] = 0.0
            self.vetoes["TACTICAL"].append("VETO_LIQUIDITY_VELOCITY_UNCOMPUTABLE")

        turnover_cr = (vol.rolling(20).mean().iloc[-1] * self.c_price) / 10000000
        self.vectors["Liquidity_Depth"] = float(max(0.0, min(turnover_cr * 4.0, 100.0)))

    def calculate_multiplicative_failure_surface(self):
        """Transforms standalone metrics into integrated joint failure probabilities"""
        close = self.df["Close"]
        high = self.df["High"]
        low = self.df["Low"]
        vol = self.df["Volume"]
        
        vol_ratio_series = (vol / vol.rolling(20).mean().clip(lower=1e-6)).dropna()
        candle_range_series = high - low
        close_location_series = ((close - low) / candle_range_series.clip(lower=1e-6)).dropna()
        ema20_series = close.rolling(20).mean().dropna()
        exhaustion_series = (close / ema20_series.clip(lower=1e-6)).dropna()

        rvol_rank = float(vol_ratio_series.tail(252).rank(pct=True).iloc[-1]) if not vol_ratio_series.empty else 0.5
        wick_rank = float((1.0 - close_location_series).tail(252).rank(pct=True).iloc[-1]) if not close_location_series.empty else 0.5
        exhaust_rank = float(exhaustion_series.tail(252).rank(pct=True).iloc[-1]) if not exhaustion_series.empty else 0.5

        p_churn = 0.65 * rvol_rank if rvol_rank > 0.75 else 0.0
        p_distribution_wick = 0.50 * wick_rank if wick_rank > 0.70 else 0.0
        p_exhaustion = 0.40 * exhaust_rank if exhaust_rank > 0.85 else 0.0
        
        joint_safety_space = (1.0 - p_churn) * (1.0 - p_distribution_wick) * (1.0 - p_exhaustion)
        compounded_risk = (1.0 - joint_safety_space)
        
        macro_amplifier = 1.50 if self.vectors["Continuous_Regime_Score"] < 45.0 else 1.0
        self.vectors["Joint_Failure_Risk"] = float(max(0.0, min(compounded_risk * macro_amplifier * 100.0, 100.0)))

    # =========================================================================
    # 5. PORTFOLIO ALLOCATION ENGINE
    # =========================================================================
    def evaluate_capital_portfolio_metrics(self):
        """Drawdown and covariance exposure allocation verification module"""
        if self.portfolio_df is None or self.portfolio_df.empty or not self.info:
            return "PASSED", 1.0
            
        try:
            asset_sector_raw = str(self.info.get("sector", "Unknown"))
            canonical_asset_sector = normalize_sector(asset_sector_raw)
            
            cols_upper = {c.upper(): c for c in self.portfolio_df.columns}
            sector_col = next((cols_upper.get(x) for x in ["SECTOR", "INDUSTRY", "THEME"] if x in cols_upper), None)
            value_col = next((cols_upper.get(x) for x in ["CURRENT VALUE", "VALUE", "AMOUNT"] if x in cols_upper), None)
            pnl_col = next((cols_upper.get(x) for x in ["UNREALIZED PNL", "GAIN", "PNL"] if x in cols_upper), None)
            cost_col = next((cols_upper.get(x) for x in ["INVESTED", "COST", "BUY_VALUE"] if x in cols_upper), None)
            
            if not sector_col or canonical_asset_sector == "OTHER" or not value_col:
                return "PASSED", 1.0

            portfolio_sectors_normalized = self.portfolio_df[sector_col].astype(str).apply(normalize_sector)
            vectorized_match = (portfolio_sectors_normalized == canonical_asset_sector)
            matching_holdings = self.portfolio_df[vectorized_match]
            
            portfolio_drawdown_coefficient = 1.0
            if cost_col and value_col:
                total_cost = self.portfolio_df[cost_col].sum()
                total_value = self.portfolio_df[value_col].sum()
                if total_cost > total_value:
                    realized_drawdown = (total_cost - total_value) / total_cost
                    drawdown_exhaustion_ratio = realized_drawdown / self.max_drawdown_limit
                    portfolio_drawdown_coefficient = max(0.0, min(1.0 - drawdown_exhaustion_ratio, 1.0))

            sector_capital = matching_holdings[value_col].sum()
            sector_concentration = sector_capital / self.total_capital
            
            if sector_concentration >= 0.25:
                self.vetoes["STRUCTURAL"].append("VETO_SECTOR_MAX_CONCENTRATION")
                return "SECTOR_MAXED", 0.0
            elif sector_concentration >= 0.12:
                portfolio_drawdown_coefficient *= (1.0 - (sector_concentration * 2.0))
                self.logs.append(f"[PORTFOLIO] Trimmed allocation units due to significant open exposure in {canonical_asset_sector}.")
                
            if pnl_col and not matching_holdings.empty:
                max_single_pnl = matching_holdings[pnl_col].dropna().max()
                if pd.notna(max_single_pnl) and max_single_pnl > (self.total_capital * 0.08):
                    portfolio_drawdown_coefficient *= 0.50

            return "PASSED", portfolio_drawdown_coefficient
        except Exception:
            return "PASSED", 1.0

    # =========================================================================
    # 6. DECISION ARBITRATION & CALIBRATION LAYERS
    # =========================================================================
    def execute_arbitration_fusion_layer(self):
        """Processes continuous state parameters to output precise position weights"""
        close = self.df["Close"]
        vol = self.df["Volume"]
        
        # Rigid nan_to_num fallbacks wiped out to expose real data failures
        for k, v in self.vectors.items():
            if pd.isna(v) or np.isinf(v):
                self.vetoes["FATAL"].append(f"VETO_DATA_CORRUPTION_{k.upper()}")

        # Segment Hard-Gate Veto Logic into a Hierarchical Severity Stack
        if self.vectors["Trend_ZScore"] < 40.0: self.vetoes["STRUCTURAL"].append("VETO_LOW_TREND_ZSCORE")
        if self.vectors["Compression_Pct"] < 40.0: self.vetoes["TACTICAL"].append("VETO_VOLATILITY_EXPANDED")
        if self.vectors["Liquidity_Velocity"] > 85.0: self.vetoes["TACTICAL"].append("VETO_VOL_ACCELERATION_SPIKE")
        if self.vectors["Liquidity_Depth"] < 30.0: self.vetoes["STRUCTURAL"].append("VETO_LIQUIDITY_INSUFFICIENT")
        if self.vectors["Joint_Failure_Risk"] >= 65.0: self.vetoes["TACTICAL"].append("VETO_INSTITUTIONAL_DISTRIBUTION_TRAP")
        if self.vectors["Quality_Stability"] < 35.0: self.vetoes["STRUCTURAL"].append("VETO_STRUCTURAL_HEALTH_FAILURE")

        portfolio_risk_status, drawdown_scale_factor = self.evaluate_capital_portfolio_metrics()

        # Volatility Range Breakout Confirmation Filters
        prior_high = close.rolling(20).max().shift(1).iloc[-1]
        volatility_expansion_passed = self.c_price > (prior_high * 0.995)
        
        vol_slope_passed = (vol.iloc[-1] > vol.iloc[-2] > vol.iloc[-3]) or (vol.iloc[-1] > vol.rolling(5).mean().iloc[-1])
        breakout_confirmed = volatility_expansion_passed and vol_slope_passed

        # Master Unified Point Distribution Formulation
        absolute_alpha_score = (
            (0.30 * self.vectors["Trend_ZScore"]) +
            (0.20 * self.vectors["Compression_Pct"]) +
            (0.20 * self.vectors["Timing_Percentile"]) +
            (0.15 * self.vectors["Volume_Sponsorship_Pct"]) +
            (0.10 * self.vectors["Continuous_Regime_Score"]) +
            (0.05 * self.vectors["RiskReward"])
        )

        # Systematic Market Calibration Layer (Relative Normalization Vector)
        self.final_alpha_score = absolute_alpha_score * (1.0 + (self.vectors["Continuous_Regime_Score"] - 50.0) / 100.0)

        # Hierarchical Signal Routing Logic
        if self.vetoes["FATAL"] or self.vetoes["STRUCTURAL"]:
            self.decision = "🔴 AVOID"
            self.allocated_sizing_pct = 0.0
        elif self.vetoes["TACTICAL"]:
            self.decision = "🟡 STANDBY"
            self.allocated_sizing_pct = 0.0
            self.logs.append("[ARBITRATION] Tactical edge variance detected. Rerouting long orders to Standby.")
        elif self.final_alpha_score >= 75.0 and breakout_confirmed and self.vectors["Continuous_Regime_Score"] >= 45.0:
            self.decision = "🟢 ENTER NOW"
            
            # Continuous Risk Sizing Allocation Gradient
            confidence_multiplier = (self.vectors["Continuous_Regime_Score"] / 100.0) * (1.0 - (self.vectors["Joint_Failure_Risk"] / 100.0))
            continuous_fraction = 100.0 * confidence_multiplier * drawdown_scale_factor
            self.allocated_sizing_pct = round(max(0.0, min(continuous_fraction, 100.0)), 1)
        else:
            self.decision = "🟡 STANDBY"
            self.allocated_sizing_pct = 0.0
            if self.final_alpha_score >= 75.0 and not breakout_confirmed:
                self.logs.append("[ARBITRATION] Coherent parameters passed; execution paused awaiting absolute range clearance.")

    def render_execution_panel(self):
        """Generates the summary dashboard output"""
        print("\n" + "=" * 60)
        print(f"🧠 ALPHA V26 QUANT PRODUCTION CORE STACK: {self.symbol}")
        print("=" * 60)
        for key, value in self.vectors.items():
            val_str = f"{round(value, 1)}/100" if pd.notna(value) else "NULL"
            print(f"📡 {key:<28} : {val_str}")
        print("-" * 60)
        print(f"🔥 CALIBRATED ALPHA VALUE     : {round(self.final_alpha_score, 1) if pd.notna(self.final_alpha_score) else 'N/A'}/100")
        print(f"🚦 UNIFIED SYSTEM DECISION     : {self.decision}")
        print(f"💰 POSITION RISK SIZING PAYLOAD: {self.allocated_sizing_pct}% TARGET CAPITAL ALLOWANCE")
        print("-" * 60)
        
        flat_vetoes = [item for sublist in self.vetoes.values() for item in sublist]
        if flat_vetoes:
            print("❌ STRATEGIC SEVERITY TIER VETOES ACTIVE:")
            for k, v_list in self.vetoes.items():
                if v_list: print(f"  • [{k} SEVERITY] -> {v_list}")
        if self.logs:
            print("📝 SYSTEM ARBITRATION OVERRIDES REPORT:")
            for log in self.logs: print(f"  • {log}")
        print("=" * 60 + "\n")

    def execute_pipeline(self):
        if not self.load_data_pipeline():
            if "VETO_DATA_COMPLETENESS_VIOLATION" in self.vetoes["FATAL"]:
                self.render_execution_panel()
            else:
                print(f"❌ Ingestion sequence failed for target asset symbol: {self.symbol}")
            return
        if not self.calculate_adaptive_state_vectors():
            print(f"❌ Math validation layers empty for trading frame: {self.symbol}")
            return
        self.compute_continuous_regime_vector()
        self.calculate_resilient_quality_liquidity()
        self.calculate_multiplicative_failure_surface()
        self.execute_arbitration_fusion_layer()
        self.render_execution_panel()


if __name__ == "__main__":
    asset_query = input("\n📌 Enter Target Ticker Assembly: ")
    engine = AlphaV26MasterEngine(asset_query)
    engine.execute_pipeline()