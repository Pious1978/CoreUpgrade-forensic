# =============================================================================
# 🚀 QUANT ALPHA PIPELINE: UNIFIED MASTER ORCHESTRATOR & TIER CALIBRATOR
# Standardizes Scoring, Re-Calibrates Tier Gates, and Ensures Cross-File Parity
# =============================================================================

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
import requests
import yfinance as yf

warnings.filterwarnings("ignore")

# =============================================================================
# SYSTEM PATHS & DIRECTORIES
# =============================================================================
BASE_DIR = r"C:\Users\GS102\OneDrive\Research\Invest"
CSV_PATH = os.path.join(BASE_DIR, "nse_eq.csv")
SCREENER_PATH = os.path.join(BASE_DIR, "screener_data.csv")
CUP_HANDLE_EXCEL = os.path.join(BASE_DIR, "INSTITUTIONAL_CUP_HANDLE.xlsx")
OUTPUT_EXCEL = os.path.join(BASE_DIR, "COMPOSITE_ALPHA_OUTPUT.xlsx")

# Expanded lookback to guarantee clearing the 252 trading day minimum
LOOKBACK = "2y"
NIFTY_SYMBOL = "^NSEI"
# Throttled batch size to prevent Yahoo Finance rate limits
BATCH_SIZE = 50

# =============================================================================
# CALIBRATED QUANTITATIVE TIER THRESHOLDS
# =============================================================================
TIER_1_SCORE = 75.0  # Leader (Actionable Breakout)
TIER_1_RS    = 80.0

TIER_2_SCORE = 62.0  # High Probability Setup
TIER_2_RS    = 65.0

TIER_3_SCORE = 50.0  # Watchlist / Developing
TIER_3_RS    = 50.0


class AlphaPipelineOrchestrator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        })
        self.nifty_series = pd.Series(dtype=float)
        self.stock_cache = {}
        self.raw_rs_map = {}

    def run_pipeline(self):
        print("======================================================================")
        print("🚀 QUANTITATIVE ALPHA PIPELINE (MASTER ORCHESTRATOR)")
        print("======================================================================\n")

        symbols = self._load_universe_symbols()
        if not symbols:
            print("❌ Execution Refused: No symbols loaded.")
            return

        print(f"📡 Loaded {len(symbols)} symbols from NSE EQ universe.")
        self._fetch_nifty_reference()
        self._ingest_ohlcv_batches(symbols)
        
        if not self.stock_cache:
            print("\n❌ Pipeline halted: Stock cache is empty.")
            return

        # 1. Deterministic Percentile Calculation
        print(f"\n[PASS 1] Calculating Deterministic RS Percentiles across {len(self.raw_rs_map)} assets...")
        rs_series = pd.Series(self.raw_rs_map)
        rs_percentiles = (rs_series.rank(method="average", pct=True) * 100.0).to_dict()

        # 2. External Fundamental Data Ingestion
        ext_fundamentals = self._load_external_fundamentals()

        # 3. Multi-Factor Scoring & Tier Calibration Pass
        print("\n[PASS 2] Evaluating Multi-Factor Matrix & Re-Calibrating Tiers...")
        results = []

        for sym, df in self.stock_cache.items():
            try:
                price = float(df["Close"].iloc[-1])
                pivot_high = float(df["High"].tail(252).max())

                # A. Pattern Quality Score (Max 30)
                s_pattern, pivot_dist_pct = self._calc_pattern_score(df, pivot_high)

                # B. Relative Strength Score (Max 25)
                rs_pctile = rs_percentiles.get(sym, 50.0)
                s_rs = round((rs_pctile / 100.0) * 25.0, 1)

                # Assign RS Grade
                if rs_pctile >= 95:    rs_grade = "A+"
                elif rs_pctile >= 90:  rs_grade = "A"
                elif rs_pctile >= 80:  rs_grade = "B"
                elif rs_pctile >= 65:  rs_grade = "C"
                elif rs_pctile >= 50:  rs_grade = "D"
                else:                      rs_grade = "F"

                # C. Continuous Volume Score (Max 20)
                s_volume, rvol, dryup_ratio = self._calc_volume_score(df)

                # D. Smooth Stage 2 & Trend Score (Max 15)
                s_trend = self._calc_trend_score(df)

                # E. Liquidity & Turnover Score (Max 10)
                recent_vol = df["Volume"].tail(20)
                recent_close = df["Close"].tail(20)
                turnover_cr = float((recent_close * recent_vol).mean() / 1e7)
                s_liquidity = min((turnover_cr / 25.0) * 10.0, 10.0)

                # Total Composite Alpha Score
                comp_score = round(s_pattern + s_rs + s_volume + s_trend + s_liquidity, 1)

                # Calibrated Tier Assignment Logic
                if comp_score >= TIER_1_SCORE and rs_pctile >= TIER_1_RS:
                    tier = "TIER-1: Leader / High Conviction"
                elif comp_score >= TIER_2_SCORE and rs_pctile >= TIER_2_RS:
                    tier = "TIER-2: High Probability Setup"
                elif comp_score >= TIER_3_SCORE and rs_pctile >= TIER_3_RS:
                    tier = "TIER-3: Watchlist / Developing"
                else:
                    tier = "TIER-4: Speculative / Avoid"

                # Metrics for Breakout Trigger Integration
                opp_display = f"{round(comp_score / 10.0, 1)}/10"
                readiness_display = f"{round(min(10.0, (comp_score / 10.0) * 1.1), 1)}/10"

                raw_sym = sym.replace(".NS", "")
                fund_data = ext_fundamentals.get(raw_sym, {})

                results.append({
                    "Ticker": raw_sym,
                    "close": round(price, 2),
                    "pivot": round(pivot_high, 2),
                    "pivot_extension": round(pivot_dist_pct, 2),
                    "Composite_Score": comp_score,
                    "Operational Classification Tier": tier,
                    "Opportunity": opp_display,
                    "Readiness": readiness_display,
                    "rs_percentile": round(rs_pctile, 1),
                    "rs_grade": rs_grade,
                    "intraday_rvol": rvol,
                    "dryup_ratio": dryup_ratio,
                    "traded_qty": int(recent_vol.iloc[-1]),
                    "turnover_cr": round(turnover_cr, 2),
                    "Score_Pattern": round(s_pattern, 1),
                    "Score_RS": s_rs,
                    "Score_Volume": round(s_volume, 1),
                    "Score_Trend": round(s_trend, 1),
                    "Score_Liquidity": round(s_liquidity, 1),
                    "Sector": fund_data.get("Sector", "Unknown"),
                    "Sales_QoQ": fund_data.get("Sales_QoQ", 0),
                    "Profit_QoQ": fund_data.get("Profit_QoQ", 0)
                })
            except Exception:
                continue

        if not results:
            print("❌ Processing failed: No results generated.")
            return

        df_out = pd.DataFrame(results).sort_values("Composite_Score", ascending=False).reset_index(drop=True)

        # 4. Export & Diagnostic Pass
        self._export_and_verify(df_out)

    # =========================================================================
    # INTERNAL CALCULATION ENGINE
    # =========================================================================
    def _load_universe_symbols(self):
        if not os.path.exists(CSV_PATH):
            return []
        try:
            df = pd.read_csv(CSV_PATH)
            df.columns = [c.strip().upper() for c in df.columns]
            if "SERIES" in df.columns:
                df = df[df["SERIES"] == "EQ"]
            symbols = df["SYMBOL"].dropna().astype(str).str.strip().str.upper().unique().tolist()
            dead = {"GATI", "LTIM", "JSWCEMENT", "PIRAMALFIN"}
            return [s + ".NS" if not s.endswith(".NS") else s for s in symbols if s not in dead]
        except:
            return []

    def _fetch_nifty_reference(self):
        try:
            nifty_df = yf.download(NIFTY_SYMBOL, period=LOOKBACK, progress=False, session=self.session)
            if 'Close' in nifty_df.columns:
                self.nifty_series = nifty_df['Close'].dropna()
                if isinstance(self.nifty_series, pd.DataFrame):
                    self.nifty_series = self.nifty_series.iloc[:, 0]
        except Exception as e:
            print(f"[⚠️] Failed fetching Nifty reference: {e}")

    def _ingest_ohlcv_batches(self, symbols):
        total = len(symbols)
        print(f"\n[PASS 0] Downloading OHLCV Data for {total} Tickers in Batches...")

        for i in range(0, total, BATCH_SIZE):
            batch = symbols[i:i + BATCH_SIZE]
            try:
                data = yf.download(
                    batch,
                    period=LOOKBACK,
                    threads=True,
                    progress=False,
                    auto_adjust=True,
                    session=self.session,
                )
            except Exception as e:
                print(f"[⚠️] Batch download HTTP exception: {e}")
                continue

            if data.empty:
                continue

            for t in batch:
                try:
                    if len(batch) > 1:
                        if isinstance(data.columns, pd.MultiIndex):
                            if hasattr(data.columns, 'levels') and t not in data.columns.get_level_values(-1) and t not in data.columns.get_level_values(0):
                                continue

                            if t in data.columns.get_level_values(0):
                                df = data[t].dropna()
                            else:
                                df = data.xs(t, axis=1, level=-1).dropna()
                        else:
                            df = data.dropna()
                    else:
                        df = data.dropna()

                    if df.empty or len(df) < 252:
                        continue

                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)

                    # Liquidity Gate (≥ ₹3 Cr Turnover)
                    avg_turnover = (df["Close"].tail(20) * df["Volume"].tail(20)).mean()
                    if avg_turnover < 3e7:
                        continue

                    self.stock_cache[t] = df

                    # Multi-Horizon Blended Excess Return vs Nifty
                    blended_rs = self._calc_blended_rs(df)
                    if blended_rs is not None:
                        self.raw_rs_map[t] = blended_rs
                except Exception as inner_e:
                    if len(self.stock_cache) == 0 and t == batch[0]:
                        print(f"[DEBUG] Dropped {t} due to error: {inner_e}")
                    continue

            print(f" -> Progress: Batch [{min(i + BATCH_SIZE, total)} / {total}] mapped. Cached valid: {len(self.stock_cache)}")
            # Increased sleep delay to prevent Yahoo Finance API rate limiting
            time.sleep(2.5)

    def _calc_blended_rs(self, df):
        if self.nifty_series.empty or len(df) < 252 or len(self.nifty_series) < 252:
            return None
        try:
            blended = 0.0
            for days, w in [(63, 0.40), (126, 0.35), (252, 0.25)]:
                stock_ret = (df["Close"].iloc[-1] / df["Close"].iloc[-days]) - 1.0
                target_date = df.index[-days]
                n_past = self.nifty_series.loc[self.nifty_series.index >= target_date]
                if n_past.empty:
                    return None
                nifty_ret = (self.nifty_series.iloc[-1] / n_past.iloc[0]) - 1.0
                blended += (stock_ret - nifty_ret) * w
            return float(blended)
        except:
            return None

    def _calc_pattern_score(self, df, pivot_high):
        price = float(df["Close"].iloc[-1])
        low_6m = float(df["Low"].tail(120).min())

        base_depth = (pivot_high - low_6m) / pivot_high * 100.0
        depth_score = 5.0 if 12.0 <= base_depth <= 35.0 else (3.0 if 35.0 < base_depth <= 45.0 else 0.0)

        handle = df["Close"].tail(15)
        handle_range = (handle.max() - handle.min()) / handle.min()
        rim_thresh = pivot_high * 0.88
        handle_score = 10.0 if (handle_range < 0.10 and handle.min() >= rim_thresh) else (6.0 if (handle_range < 0.15 and handle.min() >= rim_thresh) else 0.0)

        cup_body = df.tail(120)
        ceiling = low_6m + 0.30 * (pivot_high - low_6m)
        days_in_bottom = (cup_body["Close"] <= ceiling).sum()
        maturity_score = 8.0 if days_in_bottom >= 20 else (5.0 if days_in_bottom >= 15 else 0.0)

        pivot_dist_pct = (pivot_high - price) / pivot_high * 100.0
        pivot_score = 7.0 if price >= pivot_high else (5.0 if pivot_dist_pct <= 1.5 else (2.0 if pivot_dist_pct <= 3.0 else 0.0))

        return min(depth_score + handle_score + maturity_score + pivot_score, 30.0), round(pivot_dist_pct, 2)

    def _calc_volume_score(self, df):
        window = df.tail(135)
        if len(window) < 135:
            return 0.0, 0.0, 0.0

        handle = window.tail(15)
        cup_body = window.iloc[:-15]
        right_rim = cup_body.tail(30)
        left_rim = cup_body.head(30)

        dryup_ratio = handle["Volume"].mean() / (right_rim["Volume"].mean() + 1e-9)
        dryup_score = 6.0 if dryup_ratio <= 0.50 else (4.0 if dryup_ratio <= 0.70 else (2.0 if dryup_ratio <= 0.85 else 0.0))

        expansion_ratio = right_rim["Volume"].mean() / (left_rim["Volume"].mean() + 1e-9)
        expansion_score = min((expansion_ratio / 1.5) * 5.0, 5.0)

        rvol = float(df["Volume"].iloc[-1]) / float(df["Volume"].tail(20).mean() + 1e-9)
        rvol_score = min((rvol / 2.0) * 4.0, 4.0)

        close_diff = df["Close"].diff()
        direction = np.where(close_diff > 0, 1, np.where(close_diff < 0, -1, 0))
        obv = (direction * df["Volume"]).cumsum().tail(20)
        slope = np.polyfit(np.arange(len(obv)), obv.values, 1)[0]
        obv_score = 5.0 if slope > 0 else 0.0

        return min(dryup_score + expansion_score + rvol_score + obv_score, 20.0), round(rvol, 2), round(dryup_ratio, 2)

    def _calc_trend_score(self, df):
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

        pts = 0.0
        if e50 > e150: pts += 2.5
        if e150 > e200: pts += 2.5
        if p > e50: pts += 2.5
        if p > e200: pts += 2.5
        if e200_slope > 0: pts += 2.5
        if (p / h52) >= 0.85: pts += 2.5
        return min(pts, 15.0)

    def _load_external_fundamentals(self):
        if not os.path.exists(SCREENER_PATH):
            return {}
        try:
            df = pd.read_csv(SCREENER_PATH, index_col='Symbol')
            return df.to_dict(orient='index')
        except:
            return {}

    def _export_and_verify(self, df):
        print(f"\n💾 Writing calibrated alpha output to: {OUTPUT_EXCEL}...")
        try:
            with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Master Composite Alpha", index=False)
            print("[+] Save Success!")
        except Exception as err:
            print(f"[⚠️] Spreadsheet export error: {err}")

        # Verification Pass
        print("\n======================================================================")
        print("📊 PIPELINE RE-CALIBRATION DIAGNOSTIC SUMMARY")
        print("======================================================================")
        print(f"Total Symbols Assessed : {len(df)}")
        print("\nTier Distribution:")
        tier_counts = df["Operational Classification Tier"].value_counts()
        for tier_name, count in tier_counts.items():
            pct = (count / len(df)) * 100
            print(f"  • {tier_name:<35} : {count:>4} ({pct:.2f}%)")

        print("\nTop 5 Actionable Setups (Tier 1 / Tier 2):")
        top_picks = df[df["Operational Classification Tier"].str.contains("TIER-1|TIER-2", na=False)].head(5)
        if not top_picks.empty:
            print(top_picks[["Ticker", "close", "Composite_Score", "rs_percentile", "rs_grade", "Operational Classification Tier"]].to_string(index=False))
        else:
            print("  (No Tier 1/2 setups qualified on today's scan)")
        print("======================================================================\n")


if __name__ == "__main__":
    orchestrator = AlphaPipelineOrchestrator()
    orchestrator.run_pipeline()
