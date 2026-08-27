# ============================================================================
# BREAKOUT TRIGGER SCANNER v3.8 (Tier-Aware Adaptive Filtering Build)
# Real-Time Tactical Entry, Risk Sizing & Multi-Source Institutional Engine
# ============================================================================

import os
import re
import sys
import time
import datetime
import warnings
import pandas as pd
import numpy as np
import yfinance as yf
import logging

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Chained pattern scanner — must live in the same folder (or on sys.path)
# as this script. Import is deferred/optional: if it's missing, the smart
# chain step below just skips it and the rest of the pipeline runs as before.
try:
    import cup_handle_scanner
    CUP_HANDLE_MODULE_AVAILABLE = True
except ImportError:
    CUP_HANDLE_MODULE_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================
BASE_DIR            = r"C:\Users\GS102\OneDrive\Research\Invest"
INPUT_EXCEL         = os.path.join(BASE_DIR, "COMPOSITE_ALPHA_OUTPUT.xlsx")
FALLBACK_EXCEL      = os.path.join(BASE_DIR, "MASTER_OUTPUT.xlsx")
REPORT_EXCEL        = os.path.join(BASE_DIR, "Institutional_Breakout_Report.xlsx")
SOVEREIGN_EXCEL     = os.path.join(BASE_DIR, "SOVEREIGN_ALPHA_V24.xlsx")
EARNINGS_GAP_EXCEL  = os.path.join(BASE_DIR, "ALPHA_V14_QUANT_MATRIX.xlsx")
WATCHLIST_EXCEL     = os.path.join(BASE_DIR, "WEEKLY_WATCHLIST.xlsx")
TRADE_PLAN_EXCEL    = os.path.join(BASE_DIR, "TRADE_EXECUTION_PLAN.xlsx")
LOG_FILE            = os.path.join(BASE_DIR, "ACTIVE_BREAKOUT_ALERTS.csv")
CUP_HANDLE_EXCEL    = os.path.join(BASE_DIR, "INSTITUTIONAL_CUP_HANDLE.xlsx")

# Source-specific score thresholds applied at ingest time
MIN_GRADE_CONSOLIDATION = 55.0
MIN_GRADE_SOVEREIGN     = 18.0
MIN_GRADE_EARNINGS_GAP  = 55.0
MIN_EMERGENCE_RANK      = 30.0

# Cup & Handle chained scanner — smart-chain + ingest settings
CUP_HANDLE_MAX_AGE_HOURS = 20   # re-scan only if file missing or older than this
CUP_HANDLE_MIN_SCORE     = 55   # Discard floor (100-point scale); < 55 excluded

# Alert-time quality gates — applied inside detect_intraday_trigger()
MIN_READINESS_TIER1     = 4.0   # Relaxed baseline for Tier 1 leaders only
MIN_READINESS_STANDARD  = 5.0   # Main gate anchor for standard watch setups
MIN_OPPORTUNITY         = 5.0   # Relaxed from 5.5 to capture top metrics like MANKIND

# Hard-blocked tiers — no threshold can override these
BLOCKED_TIERS           = {"BROKEN", "Tier 3"}

RVOL_TRIGGER_LIMIT  = 1.8   # Baseline intraday volume velocity multiplier
PIVOT_BUFFER_PCT    = 1.5
RISK_PCT            = 0.005
CAPITAL             = 0.0

# Delisted / suspended symbols to skip without downloading
DEAD_SYMBOL_LIST = {
    "JSWCEMENT", "PIRAMALFIN", "SUDEEPPHRM",
    "SHRINGARMS", "GKENERGY", "VIKRAN", "BHARTIHEXA", "ACE"
}


# ============================================================================
# HELPERS
# ============================================================================
def parse_pivot_from_trigger(trigger_text: str) -> float:
    match = re.search(r"₹([\d,.]+)", str(trigger_text))
    return float(match.group(1).replace(",", "")) if match else 0.0


def parse_score(s: str) -> float:
    try:
        return float(str(s).split("/")[0].strip())
    except Exception:
        return 0.0


def parse_edp_days(edp: str) -> int:
    nums = re.findall(r"\d+", str(edp))
    return int(nums[0]) if nums else 5


def hold_guidance(readiness_score: float, edp_days: int) -> str:
    if readiness_score >= 8.5:
        days = min(60, edp_days * 6)
        return f"Up to {days} trading days — high quality, let it run."
    elif readiness_score >= 6.5:
        days = min(30, edp_days * 4)
        return f"Reassess at {days} trading days."
    else:
        days = min(15, edp_days * 3)
        return f"Hard review at {days} trading days — lower conviction setup."


def calc_position_size(capital: float, entry: float, stop: float) -> dict:
    if capital <= 0 or entry <= 0 or stop >= entry:
        return {"units": 0, "capital_used": 0, "max_loss": 0,
                "concentration": 0, "note": "Cannot size — invalid inputs."}

    risk_amount    = capital * RISK_PCT
    risk_per_share = entry - stop
    raw_units      = int(risk_amount / risk_per_share)
    cap_units      = int((capital * 0.20) / entry)
    units          = min(raw_units, cap_units)

    if units <= 0:
        return {"units": 0, "capital_used": 0, "max_loss": 0,
                "concentration": 0,
                "note": "Position too small for capital/risk combination."}

    capital_used  = round(units * entry, 2)
    max_loss      = round(units * risk_per_share, 2)
    concentration = round((capital_used / capital) * 100, 2)
    capped        = raw_units > cap_units

    return {
        "units":         units,
        "capital_used":  capital_used,
        "max_loss":      max_loss,
        "concentration": concentration,
        "note": ("⚠️ Units capped at 20% concentration limit." if capped else "")
    }


def _is_blocked_tier(tier_string: str) -> bool:
    """Returns True if the tier should unconditionally suppress the alert."""
    for blocked in BLOCKED_TIERS:
        if blocked in tier_string:
            return True
    return False


# ============================================================================
# UNIVERSE INGEST — watch wide, alert narrow
# ============================================================================
def _build_empty_node(ticker_clean: str) -> dict:
    return {
        "Ticker":                          ticker_clean,
        "Operational Classification Tier": "Tier 1 — Ready to Monitor Daily",
        "Opportunity":                     "6.0/10",
        "Readiness":                       "7.0/10",
        "RS_Rank_Raw":                     "",
        "Expected Days to Pivot (EDP)":    "1 Trading Day",
        "14d ATR":                         "2.5%",
        "Actionable Operational Trigger":  "",
        "Composite_Grade":                 0.0,
        "_source":                         "",
        "_priority":                       99,
    }


def _ingest_master_terminal(pool: dict):
    target_file = INPUT_EXCEL if os.path.exists(INPUT_EXCEL) else FALLBACK_EXCEL
    if not os.path.exists(target_file):
        print(f"[⚠️] Master Terminal output not found — skipping.")
        return
    try:
        df = pd.read_excel(target_file)
        df.columns = df.columns.str.strip()
        for col in ["Stock", "Symbol", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break
        if "Ticker" not in df.columns:
            return

        count = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = "Master Terminal"
            node["_priority"] = 1

            for k in ["Operational Classification Tier", "Tier_Lifecycle"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["Operational Classification Tier"] = str(row[k])
            for k in ["Opportunity", "Opportunity_Display"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["Opportunity"] = str(row[k])
            for k in ["Readiness", "Readiness_Display"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["Readiness"] = str(row[k])
            for k in ["Expected Days to Pivot (EDP)", "EDP_Window"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["Expected Days to Pivot (EDP)"] = str(row[k])
            for k in ["14d ATR", "ATR_14d"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["14d ATR"] = str(row[k])
            for k in ["Actionable Operational Trigger",
                       "Actionable_Operational_Trigger"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["Actionable Operational Trigger"] = str(row[k])

            pool[clean] = node
            count += 1

        print(f"[+] Master Terminal          : {count} stocks loaded")
    except Exception as e:
        print(f"[⚠️] Could not load Master Terminal output: {e}")


def _ingest_breakout_report(pool: dict):
    if not os.path.exists(REPORT_EXCEL):
        print(f"[⚠️] Institutional_Breakout_Report not found — skipping.")
        return
    try:
        df = pd.DataFrame()
        sheet_used = ""
        for sheet in ["COILED (Tier1 Ready)", "TIGHTENING (Tier1 Watch)",
                       "All Setups"]:
            try:
                df = pd.read_excel(REPORT_EXCEL, sheet_name=sheet)
                df.columns = df.columns.str.strip()
                sheet_used = sheet
                break
            except Exception:
                continue

        if df.empty:
            return

        for col in ["Stock", "Symbol", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break

        score_col = "Score" if "Score" in df.columns else None
        before = len(df)
        if score_col:
            df = df[df[score_col] >= MIN_GRADE_CONSOLIDATION]

        count_new = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue
            if clean in pool and pool[clean].get("_priority", 99) < 2:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = f"Consolidation Scanner ({sheet_used})"
            node["_priority"] = 2

            if "Pivot" in df.columns and pd.notna(row.get("Pivot")):
                try:
                    pv = float(row["Pivot"])
                    node["Actionable Operational Trigger"] = (
                        f"🔥 ACTIVE TRIGGER - Buy breakout above ₹{pv} "
                        f"on Vol > 1.8x"
                    )
                except Exception:
                    pass
            for k in ["14d ATR", "ATR%", "ATR_Pct"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["14d ATR"] = f"{str(row[k]).replace('%','').strip()}%"
                    break
            if score_col and pd.notna(row.get(score_col)):
                node["Composite_Grade"] = float(row[score_col])

            pool[clean] = node
            count_new += 1

        print(f"[+] Institutional_Breakout   : {before} → "
              f"{count_new} stocks loaded (sheet: {sheet_used}, "
              f"Score >= {MIN_GRADE_CONSOLIDATION})")
    except Exception as e:
        print(f"[⚠️] Could not load Institutional_Breakout_Report: {e}")


def _ingest_sovereign_alpha(pool: dict):
    if not os.path.exists(SOVEREIGN_EXCEL):
        print(f"[⚠️] SOVEREIGN_ALPHA_V24.xlsx not found — skipping.")
        return
    try:
        df = pd.read_excel(SOVEREIGN_EXCEL)
        df.columns = df.columns.str.strip()
        for col in ["Stock", "Symbol", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break
        if "Ticker" not in df.columns:
            return

        before = len(df)
        if "Setup" in df.columns:
            df = df[df["Setup"].astype(str).str.contains(
                "BREAKOUT", case=False, na=False
            )]
        alpha_col = "Alpha" if "Alpha" in df.columns else None
        if alpha_col:
            df = df[df[alpha_col] >= MIN_GRADE_SOVEREIGN]
        if "Grade" in df.columns:
            df = df[df["Grade"].astype(str).str.strip().isin(["A", "B"])]

        count_new = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue
            if clean in pool and pool[clean].get("_priority", 99) < 3:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = "Hybrid Alpha (SOVEREIGN_ALPHA_V24)"
            node["_priority"] = 3

            if "RS Rnk" in df.columns and pd.notna(row.get("RS Rnk")):
                node["RS_Rank_Raw"] = str(row["RS Rnk"])
            if alpha_col and pd.notna(row.get(alpha_col)):
                node["Composite_Grade"] = round(
                    float(row[alpha_col]) / 30.0 * 100.0, 1
                )
            if "Z-Mom %" in df.columns and pd.notna(row.get("Z-Mom %")):
                try:
                    node["Opportunity"] = (
                        f"{round(float(row['Z-Mom %']) / 10.0, 1)}/10"
                    )
                except Exception:
                    pass

            pool[clean] = node
            count_new += 1

        print(f"[+] SOVEREIGN_ALPHA_V24      : {before} → "
              f"{count_new} BREAKOUT setups loaded")
    except Exception as e:
        print(f"[⚠️] Could not load SOVEREIGN_ALPHA_V24.xlsx: {e}")


def _ingest_earnings_gap(pool: dict):
    if not os.path.exists(EARNINGS_GAP_EXCEL):
        print(f"[⚠️] ALPHA_V14_QUANT_MATRIX.xlsx not found — skipping.")
        return
    try:
        df = pd.read_excel(EARNINGS_GAP_EXCEL)
        df.columns = df.columns.str.strip()
        for col in ["Symbol", "Stock", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break
        if "Ticker" not in df.columns:
            return

        before = len(df)
        score_col = "Score" if "Score" in df.columns else None
        if score_col:
            df = df[df[score_col] >= MIN_GRADE_EARNINGS_GAP]
        if "Signal" in df.columns:
            df = df[~df["Signal"].astype(str).str.contains(
                "AVOID|WEAK", case=False, na=False
            )]

        count_new = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue
            if clean in pool and pool[clean].get("_priority", 99) < 4:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = "Earnings Gap Scanner"
            node["_priority"] = 4

            if "RS_Rnk" in df.columns and pd.notna(row.get("RS_Rnk")):
                node["RS_Rank_Raw"] = str(row["RS_Rnk"])
            if "Read%" in df.columns and pd.notna(row.get("Read%")):
                try:
                    read_pct = float(
                        str(row["Read%"]).replace("%", "")
                    )
                    node["Readiness"] = (
                        f"{round(read_pct / 10.0, 1)}/10"
                    )
                except Exception:
                    pass
            if score_col and pd.notna(row.get(score_col)):
                node["Composite_Grade"] = float(row[score_col])
            if "Signal" in df.columns and pd.notna(row.get("Signal")):
                node["Operational Classification Tier"] = (
                    f"Earnings Setup — {row['Signal']}"
                )
            if "Type" in df.columns and pd.notna(row.get("Type")):
                node["Opportunity"] = f"{row['Type']} Setup"

            pool[clean] = node
            count_new += 1

        print(f"[+] ALPHA_V14_QUANT_MATRIX   : {before} → "
              f"{count_new} earnings setups loaded")
    except Exception as e:
        print(f"[⚠️] Could not load ALPHA_V14_QUANT_MATRIX.xlsx: {e}")


def _ingest_emerging_leaders(pool: dict):
    if not os.path.exists(WATCHLIST_EXCEL):
        print(f"[⚠️] WEEKLY_WATCHLIST.xlsx not found — skipping.")
        return
    try:
        df = pd.read_excel(WATCHLIST_EXCEL)
        df.columns = df.columns.str.strip()
        for col in ["Symbol", "Stock", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break
        if "Ticker" not in df.columns:
            return

        before = len(df)
        rank_col = "Emergence Rank" if "Emergence Rank" in df.columns else None
        if rank_col:
            df = df[df[rank_col] >= MIN_EMERGENCE_RANK]
        if "Signal" in df.columns:
            df = df[df["Signal"].astype(str).str.contains(
                "FUTURE LEADER|EMERGING|LEADER", case=False, na=False
            )]

        count_new = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue
            if clean in pool and pool[clean].get("_priority", 99) < 5:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = "Emerging Leaders (Weekly)"
            node["_priority"] = 5

            pivot_reconstructed = False
            for dist_col in ["Pivot Dist Display", "Pivot Dist %",
                              "Pivot_Dist", "From High % Display"]:
                if dist_col in df.columns and pd.notna(row.get(dist_col)):
                    try:
                        price_col = next(
                            (pc for pc in ["Price", "Close", "LTP"]
                             if pc in df.columns), None
                        )
                        if price_col:
                            price_val = float(row[price_col])
                            dist_pct  = float(
                                str(row[dist_col])
                                .replace("%", "")
                                .replace("−", "-")
                                .strip()
                            ) / 100.0
                            pivot_val = (
                                price_val / (1.0 + dist_pct)
                                if dist_pct < 0
                                else price_val * (1.0 + dist_pct)
                            )
                            node["Actionable Operational Trigger"] = (
                                f"🔥 ACTIVE TRIGGER - Buy breakout above "
                                f"₹{round(pivot_val, 2)} on Vol > 1.8x"
                            )
                            pivot_reconstructed = True
                            break
                    except Exception:
                        pass
                if pivot_reconstructed:
                    break

            for k in ["ATR %", "ATR%", "ATR_Pct"]:
                if k in df.columns and pd.notna(row.get(k)):
                    node["14d ATR"] = (
                        f"{str(row[k]).replace('%', '').strip()}%"
                    )
                    break
            if rank_col and pd.notna(row.get(rank_col)):
                try:
                    node["Opportunity"] = f"{round(float(row[rank_col]) / 10.0, 1)}/10"
                    node["Composite_Grade"] = float(row[rank_col])
                except Exception:
                    pass
            if "Accum Ratio" in df.columns and pd.notna(
                row.get("Accum Ratio")
            ):
                try:
                    node["Readiness"] = (
                        f"{min(10.0, round(float(row['Accum Ratio']) * 8.0, 1))}/10"
                    )
                except Exception:
                    pass

            node["Operational Classification Tier"] = (
                "Emerging Leader — Pre-Breakout Phase"
            )
            node["Expected Days to Pivot (EDP)"] = "10–20 Trading Days"

            pool[clean] = node
            count_new += 1

        print(f"[+] WEEKLY_WATCHLIST         : {before} → "
              f"{count_new} emerging leaders loaded")
    except Exception as e:
        print(f"[⚠️] Could not load WEEKLY_WATCHLIST.xlsx: {e}")


def _maybe_run_cup_handle_scan():
    """
    Smart chain: only re-runs the full NSE cup & handle scan (2400+ symbols)
    if INSTITUTIONAL_CUP_HANDLE.xlsx is missing or older than
    CUP_HANDLE_MAX_AGE_HOURS. Otherwise skips straight to ingesting today's
    already-fresh file — avoids delaying the live monitor's market-open
    start with a redundant multi-minute scan every launch.
    """
    if not CUP_HANDLE_MODULE_AVAILABLE:
        print("[⚠️] cup_handle_scanner.py not found alongside this script "
              "— skipping chained scan, will use existing file if present.")
        return

    needs_scan = True
    if os.path.exists(CUP_HANDLE_EXCEL):
        age_hours = (
            time.time() - os.path.getmtime(CUP_HANDLE_EXCEL)
        ) / 3600.0
        if age_hours < CUP_HANDLE_MAX_AGE_HOURS:
            needs_scan = False
            print(f"[+] Cup & Handle scan is fresh ({age_hours:.1f}h old) "
                  f"— skipping re-scan, using existing file.")

    if needs_scan:
        print("[*] Cup & Handle scan missing/stale — running full scan now "
              "(this may take a few minutes)...")
        try:
            cup_handle_scanner.run(output_dir=BASE_DIR)
        except Exception as e:
            print(f"[⚠️] Chained cup & handle scan failed: {e} "
                  f"— continuing without it.")


def _ingest_cup_handle(pool: dict):
    if not os.path.exists(CUP_HANDLE_EXCEL):
        print(f"[⚠️] INSTITUTIONAL_CUP_HANDLE.xlsx not found — skipping.")
        return
    try:
        df = pd.read_excel(CUP_HANDLE_EXCEL)
        df.columns = df.columns.str.strip()
        for col in ["stock", "Stock", "Symbol", "Ticker"]:
            if col in df.columns:
                df.rename(columns={col: "Ticker"}, inplace=True)
                break
        if "Ticker" not in df.columns:
            return

        before = len(df)
        if "score" in df.columns:
            df = df[df["score"] >= CUP_HANDLE_MIN_SCORE]

        count_new = 0
        for _, row in df.iterrows():
            raw = str(row.get("Ticker", "")).strip().upper()
            if not raw or raw == "NAN":
                continue
            clean = raw.replace(".NS", "")
            if clean in DEAD_SYMBOL_LIST:
                continue
            # Priority 6 — lowest precedence, only fills gaps the other
            # 5 sources didn't already flag for this ticker.
            if clean in pool and pool[clean].get("_priority", 99) < 6:
                continue

            node = _build_empty_node(clean)
            node["_source"]   = "Cup & Handle Scanner"
            node["_priority"] = 6

            score = float(row.get("score", 0))

            # 100-Point Quality Tiers
            if score >= 85:
                node["Operational Classification Tier"] = "Institutional — Cup & Handle Confirmed"
            elif score >= 75:
                node["Operational Classification Tier"] = "Tier 1 — Cup & Handle Confirmed"
            elif score >= 65:
                node["Operational Classification Tier"] = "Tier 2 — Cup & Handle Watch"
            else:
                node["Operational Classification Tier"] = "Watch — Cup & Handle Building"

            # Direct mapping from 100-point composite score
            node["Composite_Grade"] = round(score, 1)
            node["Opportunity"]     = f"{round(score / 10.0, 1)}/10"

            gap_pct = None
            price_val = row.get("price")
            pivot_val = row.get("pivot")
            if pd.notna(price_val) and pd.notna(pivot_val) and float(price_val) > 0:
                gap_pct = max(0.0, (float(pivot_val) / float(price_val) - 1.0) * 100.0)

            if gap_pct is None:
                # No price/pivot data to compute proximity — fall back to estimates
                node["Expected Days to Pivot (EDP)"] = (
                    "1–5 Trading Days" if score >= 75
                    else "5–15 Trading Days"
                )
                proximity_penalty = 0.0
            elif gap_pct < 3.0:
                node["Expected Days to Pivot (EDP)"] = "1–3 Trading Days"
                proximity_penalty = 0.0
            elif gap_pct < 8.0:
                node["Expected Days to Pivot (EDP)"] = "3–8 Trading Days"
                proximity_penalty = 1.0
            else:
                node["Expected Days to Pivot (EDP)"] = "8–15+ Trading Days"
                proximity_penalty = 2.5

            if gap_pct is not None:
                node["Gap_to_Pivot_Pct"] = round(gap_pct, 2)

            # Updated Readiness Confirmation Check
            confirmations = sum(
                bool(row.get(k)) for k in
                ["rim_ok", "base_mature_u", "vol_symmetry"]
            )
            
            rs_pctile = row.get("rs_pctile", 50)
            raw_excess = row.get("nifty_excess_6m_%")
            
            # Reinstated confirmation point using exact percentile threshold
            if pd.notna(rs_pctile) and float(rs_pctile) >= 80:
                confirmations += 1
                
            base_readiness = 4.0 + confirmations * 1.5
            readiness_val = max(1.0, min(10.0, base_readiness - proximity_penalty))
            node["Readiness"] = f"{round(readiness_val, 1)}/10"

            # Formatted exact RS Percentile String
            if pd.notna(rs_pctile):
                node["RS_Rank_Raw"] = f"{round(float(rs_pctile), 1)} Percentile"

            if "pivot" in df.columns and pd.notna(row.get("pivot")):
                try:
                    pv = float(row["pivot"])
                    node["Actionable Operational Trigger"] = (
                        f"🔥 ACTIVE TRIGGER - Buy breakout above ₹{pv} "
                        f"on Vol > 1.8x"
                    )
                except Exception:
                    pass

            pool[clean] = node
            count_new += 1

        print(f"[+] Cup & Handle Scanner     : {before} → "
              f"{count_new} setups loaded (score >= {CUP_HANDLE_MIN_SCORE}, "
              f"priority 6 — gap-fill only)")
    except Exception as e:
        print(f"[⚠️] Could not load INSTITUTIONAL_CUP_HANDLE.xlsx: {e}")


def load_tactical_universe() -> tuple:
    """
    Watch wide, alert narrow.
    Ingest functions load everything that passes source-specific score
    thresholds. Quality gates (Readiness, Opportunity, Tier) are applied
    inside detect_intraday_trigger() at alert time — not here.
    """
    print("\n[*] Loading tactical universe from all sources...")
    pool = {}

    _ingest_master_terminal(pool)
    _ingest_breakout_report(pool)
    _ingest_sovereign_alpha(pool)
    _ingest_earnings_gap(pool)
    _ingest_emerging_leaders(pool)

    # Chained pattern scan — runs only if today's output is missing/stale,
    # then ingests at lowest priority (gap-fill only, see docstring above).
    _maybe_run_cup_handle_scan()
    _ingest_cup_handle(pool)

    if not pool:
        print("[-] No stocks loaded. Run evening pipeline first.")
        return pd.DataFrame(), {}

    master_df = pd.DataFrame(list(pool.values()))
    master_df["Ticker_YF"] = master_df["Ticker"].apply(
        lambda x: x + ".NS"
    )

    source_counts = master_df["_source"].value_counts()
    print(f"\n[+] MONITORING UNIVERSE: {len(master_df)} unique stocks")
    for src, count in source_counts.items():
        print(f"    {count:>4}  {src}")
    print(f"\n    Alert gates (applied at alert time, not load time):")
    print(f"    Readiness Check: Tier-Aware (Tier 1: >= {MIN_READINESS_TIER1} | Standard: >= {MIN_READINESS_STANDARD})")
    print(f"    Opportunity >= {MIN_OPPORTUNITY} | Tier: not BROKEN, not Tier 3\n")

    trade_plan_map = {}
    if os.path.exists(TRADE_PLAN_EXCEL):
        try:
            tp = pd.read_excel(TRADE_PLAN_EXCEL)
            tp.columns = tp.columns.str.strip()
            for _, row in tp.iterrows():
                sym = str(row.get("Symbol", "")).strip().upper()
                if sym:
                    trade_plan_map[sym] = {
                        "measured_move": row.get("Measured Move", 0),
                        "mid_target":    row.get("Mid Target", 0),
                        "stop":          row.get("Stop", 0),
                    }
            print(f"[+] Trade plan: {len(trade_plan_map)} pre-calculated "
                  f"targets loaded.")
        except Exception as e:
            print(f"[⚠️] Trade plan load failed: {e} — ATR fallback.")

    return master_df.reset_index(drop=True), trade_plan_map


# ============================================================================
# INTRADAY TRIGGER DETECTION
# ============================================================================
def _fetch_weekly_volume_context(symbol: str) -> dict:
    """
    Downloads weekly OHLCV for the past 3 months and returns trailing weekly metrics.
    Returns None if data unavailable — caller treats as non-blocking.
    """
    try:
        wdf = yf.download(
            symbol, period="3mo", interval="1wk",
            progress=False, threads=False
        )
        if wdf is None or wdf.empty or len(wdf) < 5:
            return None
        if isinstance(wdf.columns, pd.MultiIndex):
            wdf.columns = wdf.columns.get_level_values(0)
        wdf = wdf.dropna()
        vol = wdf["Volume"]
        current_week_vol = float(vol.iloc[-1])
        avg_4wk          = float(vol.iloc[-5:-1].mean())
        weekly_rvol      = round(
            current_week_vol / avg_4wk, 2
        ) if avg_4wk > 0 else 1.0
        return {
            "current_week_vol": int(current_week_vol),
            "avg_4wk_vol":      int(avg_4wk),
            "weekly_rvol":      weekly_rvol,
        }
    except Exception:
        return None


def detect_intraday_trigger(symbol: str, target_data: dict,
                            trade_plan_map: dict,
                            capital: float) -> dict | None:
    try:
        # ── Alert-time quality gates ───────────────────────────────────────
        tier_str = str(target_data.get(
            "Operational Classification Tier", ""
        ))
        if _is_blocked_tier(tier_str):
            return None   # BROKEN / Tier 3 structural block check

        readiness_score = parse_score(
            target_data.get("Readiness", "7.0/10")
        )
        
        # 🛡️ 1. ADJUSTMENT: Tier-Aware Readiness Gate Pass
        if "Institutional" in tier_str or "Tier 1" in tier_str:
            if readiness_score < MIN_READINESS_TIER1:
                return None
        elif "Tier 2" in tier_str:
            if readiness_score < MIN_READINESS_STANDARD:
                return None
        else:
            if readiness_score < MIN_READINESS_STANDARD:
                return None

        # 🛡️ 2. ADJUSTMENT: Lowered Opportunity Limit Gate Pass
        opportunity_str = str(target_data.get("Opportunity", "6.0/10"))
        opportunity_score = parse_score(opportunity_str)
        is_earnings_stock = "Earnings Setup" in tier_str
        if not is_earnings_stock:
            # Earnings stocks use text like "Silent Setup" — can't parse,
            # so exempt them from the numeric Opportunity filter.
            # They are still blocked by Readiness and RVOL gates.
            if opportunity_score < MIN_OPPORTUNITY:
                return None
        # ── End quality gates ──────────────────────────────────────────────

        df = yf.download(
            symbol, period="5d", interval="5m",
            progress=False, threads=False
        )
        if df is None or df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()

        current_price = float(df["Close"].iloc[-1])
        current_vol   = float(df["Volume"].iloc[-1])

        trigger_text     = target_data.get(
            "Actionable Operational Trigger", ""
        )
        historical_pivot = parse_pivot_from_trigger(trigger_text)
        if not historical_pivot or historical_pivot <= 0:
            historical_pivot = float(df["High"].iloc[:-5].max())

        is_breaking_out      = current_price >= historical_pivot
        distance_above_pivot = (
            (current_price - historical_pivot) / historical_pivot
        ) * 100

        if not is_breaking_out:
            return None

        # Intraday RVOL velocity calculations
        avg_intraday_vol = df["Volume"].iloc[-21:-1].mean()
        rvol = (
            current_vol / avg_intraday_vol
            if avg_intraday_vol > 0 else 1.0
        )
        
        # 🛡️ 3. ADJUSTMENT: Escalate volume multiplier gate to offset low readiness thresholds
        effective_rvol_limit = (
            2.0 if ("Tier 1" in tier_str and readiness_score < 5.0)
            else RVOL_TRIGGER_LIMIT
        )
        if rvol < effective_rvol_limit:
            return None

        # Macro weekly volume background check — exceptions for high-readiness coils
        weekly_vol = None
        if readiness_score < 8.5:
            weekly_vol = _fetch_weekly_volume_context(symbol)

        # Fakeout script metrics
        vwap_series = (
            (df["Close"] * df["Volume"]).rolling(10).sum() /
            (df["Volume"].rolling(10).sum() + 1e-8)
        )
        above_vwap   = bool(current_price > vwap_series.iloc[-1])
        candle_body  = abs(current_price - float(df["Open"].iloc[-1]))
        candle_range = float(
            df["High"].iloc[-1] - df["Low"].iloc[-1]
        ) + 1e-8
        body_ratio   = candle_body / candle_range

        volume_confirmed = bool(rvol >= effective_rvol_limit)
        price_sustained  = bool(above_vwap and body_ratio >= 0.40)

        if volume_confirmed and price_sustained:
            verdict = "🔥 VALID BREAKOUT"
        elif volume_confirmed and not price_sustained:
            verdict = "⚠️ FAKEOUT TRAP (Selling Wick)"
        else:
            return None

        raw_atr_str = str(
            target_data.get("14d ATR", "2.5%")
        ).replace("%", "")
        try:    atr_pct = float(raw_atr_str)
        except: atr_pct = 2.5

        risk_unit  = historical_pivot * (atr_pct / 100.0)
        sym_clean  = symbol.replace(".NS", "").upper()
        plan_entry = trade_plan_map.get(sym_clean, {})

        stop_loss = (
            float(plan_entry["stop"])
            if plan_entry.get("stop") and float(plan_entry["stop"]) > 0
            else round(historical_pivot - risk_unit, 2)
        )
        target_1 = (
            float(plan_entry["mid_target"])
            if plan_entry.get("mid_target")
            and float(plan_entry["mid_target"]) > 0
            else round(historical_pivot + (2.0 * risk_unit), 2)
        )
        target_2 = (
            float(plan_entry["measured_move"])
            if plan_entry.get("measured_move")
            and float(plan_entry["measured_move"]) > 0
            else round(historical_pivot + (4.0 * risk_unit), 2)
        )
        target_source = "Trade Plan" if plan_entry else "ATR Estimate"

        remaining_reward_pct = (
            (target_1 - current_price) / current_price
        ) * 100
        remaining_risk_pct = (
            (current_price - stop_loss) / current_price
        ) * 100
        remaining_r_multiple = remaining_reward_pct / (
            remaining_risk_pct + 1e-8
        )
        dist_to_t1 = (
            (target_1 - current_price) / current_price
        ) * 100
        dist_to_t2 = (
            (target_2 - current_price) / current_price
        ) * 100

        # High conviction override — premium setups get wider R:R tolerance
        high_conviction = (readiness_score >= 8.5 and opportunity_score >= 8.0)
        min_r_for_entry = 1.2 if high_conviction else 1.5

        over_extended = (
            current_price > historical_pivot * (
                1.0 + PIVOT_BUFFER_PCT / 100.0
            ) or remaining_r_multiple < min_r_for_entry
        )
        if over_extended:
            verdict = "⚠️ BREAKOUT EXTENDED"

        sizing = calc_position_size(capital, current_price, stop_loss)

        edp_str  = str(target_data.get(
            "Expected Days to Pivot (EDP)", "5"
        ))
        edp_days = parse_edp_days(edp_str)

        if "Emerging Leader" in tier_str:
            hold_note = (
                f"Up to {edp_str} — long-horizon emergence structure. "
                f"Look for multi-week trend run."
            )
        else:
            hold_note = hold_guidance(readiness_score, edp_days)

        source_tag  = str(target_data.get("_source", ""))
        rs_rank_raw = str(target_data.get("RS_Rank_Raw", ""))

        return {
            "Ticker":        sym_clean,
            "Timestamp":     datetime.datetime.now().strftime("%H:%M:%S"),
            "Source":        source_tag,
            "Price":         round(current_price, 2),
            "Pivot":         round(historical_pivot, 2),
            "Ext%":          round(distance_above_pivot, 2),
            "Intraday_RVOL": round(rvol, 2),
            "Weekly_RVOL":   (weekly_vol["weekly_rvol"] if weekly_vol else "N/A" if readiness_score < 8.5 else "Bypassed (Mature Base)"),
            "Status":        verdict,
            "Entry":         round(current_price, 2),
            "Stop_Loss":     round(stop_loss, 2),
            "Target_1":      round(target_1, 2),
            "Target_2":      round(target_2, 2),
            "Target_Source": target_source,
            "Dist_T1%":      round(dist_to_t1, 1),
            "Dist_T2%":      round(dist_to_t2, 1),
            "Remaining_R":   round(remaining_r_multiple, 2),
            "Units":         sizing["units"],
            "Capital_Used":  sizing["capital_used"],
            "Max_Loss_Rs":   sizing["max_loss"],
            "Concentration": sizing["concentration"],
            "Sizing_Note":   sizing["note"],
            "EDP":           edp_str,
            "Hold_Period":   hold_note,
            "Tier":          tier_str,
            "Opportunity":   opportunity_str,
            "Readiness":     target_data.get("Readiness", "7.0/10"),
            "RS_Rank":       rs_rank_raw,
        }

    except Exception:
        return None


# ============================================================================
# CONSOLE ALERT FORMATTER
# ============================================================================
def print_alert(alert: dict):
    sep  = "=" * 66
    dash = "-" * 66

    print(f"\n🚨 {sep}")
    print(
        f"  [{alert['Timestamp']}]  {alert['Ticker']}"
        + (f"  ·  {alert['Source']}" if alert.get("Source") else "")
    )
    print(dash)
    print(f"  STATUS        : {alert['Status']}")
    print(
        f"  Current Price : ₹{alert['Price']}  |  "
        f"Pivot: ₹{alert['Pivot']}  |  "
        f"Ext: {alert['Ext%']}%"
    )
    print(f"  Intraday RVOL : {alert['Intraday_RVOL']}×"
          + (f"  |  Weekly RVOL: {alert['Weekly_RVOL']}×"
             if alert.get("Weekly_RVOL") not in (None, "N/A", "Bypassed (Mature Base)")
             else ""))
    print(dash)

    if "EXTENDED" in alert["Status"]:
        print(
            f"  ❌ SIZING REJECTED — Remaining reward only {alert['Remaining_R']}R."
        )
        print(f"     Entry over-extended. Do not buy.")
        print(f"     Wait for pullback toward ₹{alert['Pivot']}.")
    else:
        print(f"  📥 Entry        : ₹{alert['Entry']}")
        print(f"  🛑 Stop Loss    : ₹{alert['Stop_Loss']}")
        print(
            f"  🎯 Target 1     : ₹{alert['Target_1']}  "
            f"(+{alert['Dist_T1%']}% away)  [{alert['Target_Source']}]"
        )
        print(
            f"  🚀 Target 2     : ₹{alert['Target_2']}  "
            f"(+{alert['Dist_T2%']}% away)"
        )
        print(f"  ⚖️  Remaining R  : {alert['Remaining_R']}×")
        print(dash)

        if alert["Units"] > 0:
            print(f"  📦 Units        : {alert['Units']} shares")
            print(
                f"  💰 Capital Used : ₹{alert['Capital_Used']:,.0f}  "
                f"({alert['Concentration']}% of portfolio)"
            )
            print(
                f"  📉 Max Loss     : ₹{alert['Max_Loss_Rs']:,.0f}  "
                f"(0.5% rule)"
            )
            if alert["Sizing_Note"]:
                print(f"  ⚠️  {alert['Sizing_Note']}")
        else:
            print(f"  📦 Position Size: {alert['Sizing_Note']}")

        print(dash)
        print(f"  ⏳ Hold Period  : {alert['Hold_Period']}")
        print(
            f"  🎯 Exit Strategy: Sell 50% at T1 → "
            f"Move stop to breakeven → Trail to T2"
        )

    print(dash)
    print(f"  🧠 Tier          : {alert['Tier']}")
    opp_line = (
        f"  📊 Opportunity  : {alert['Opportunity']}  |  "
        f"Readiness: {alert['Readiness']}  |  "
        f"EDP: {alert['EDP']}"
    )
    if alert.get("RS_Rank"):
        opp_line += f"  |  RS Rank: {alert['RS_Rank']}"
    print(opp_line)
    print(f"🚨 {sep}\n")


# ============================================================================
# MAIN MONITORING LOOP
# ============================================================================
def execute_live_monitoring_loop(capital: float):
    print("\n" + "=" * 66)
    print("🎯  LIVE TACTICAL TRIGGER ENGINE  (Sniping Mode v3.8 adaptive)")
    print("=" * 66)
    print(
        f"    Capital : ₹{capital:,.0f}  |  "
        f"Risk/trade : ₹{capital * RISK_PCT:,.0f}  (0.5%)\n"
    )

    universe_df, trade_plan_map = load_tactical_universe()
    if universe_df.empty:
        return

    universe_df.set_index("Ticker", inplace=True)
    target_tickers = universe_df.index.tolist()

    print(f"[*] Monitoring {len(target_tickers)} targets.")
    print("[*] Press Ctrl+C to stop.\n")

    triggered_cache = set()
    MARKET_OPEN     = datetime.time(9, 15)
    MARKET_CLOSE    = datetime.time(15, 30)

    now = datetime.datetime.now()
    if now.time() < MARKET_OPEN:
        open_dt    = datetime.datetime.combine(now.date(), MARKET_OPEN)
        total_wait = int((open_dt - now).total_seconds())
        print(f"[*] Pre-market — launched at {now.strftime('%H:%M:%S')} IST")
        print(
            f"[*] First scan fires at 9:15:00 AM IST "
            f"({total_wait}s from now)."
        )
        print(f"[*] Holding on warm thread — press Ctrl+C to abort.\n")
        while datetime.datetime.now().time() < MARKET_OPEN:
            remaining = int(
                (
                    datetime.datetime.combine(
                        datetime.date.today(), MARKET_OPEN
                    ) - datetime.datetime.now()
                ).total_seconds()
            )
            if remaining % 30 == 0:
                print(
                    f"    ⏳ {remaining}s to open "
                    f"[{datetime.datetime.now().strftime('%H:%M:%S')}]"
                )
            time.sleep(15)
        print(f"\n🔔 MARKET OPEN — initiating first scan now.\n")

    while True:
        current_time = datetime.datetime.now().time()

        if current_time > MARKET_CLOSE:
            print(
                f"\n[*] Market closed at "
                f"{current_time.strftime('%H:%M:%S')} IST."
            )
            print(f"[*] {len(triggered_cache)} unique alerts fired today.")
            print(f"[*] Full log saved to: {LOG_FILE}")
            print("[*] Scanner shutting down.\n")
            break

        print(
            f"🔄  Scanning {len(target_tickers)} targets "
            f"[{datetime.datetime.now().strftime('%H:%M:%S')}]..."
        )

        for ticker in target_tickers:
            meta      = (universe_df.loc[ticker].to_dict()
                         if ticker in universe_df.index else {})
            yf_symbol = ticker + ".NS"

            alert = detect_intraday_trigger(
                yf_symbol, meta, trade_plan_map, capital
            )

            if alert:
                cache_key = f"{alert['Ticker']}_{alert['Status']}"
                if cache_key not in triggered_cache:
                    triggered_cache.add(cache_key)
                    print_alert(alert)
                    pd.DataFrame([alert]).to_csv(
                        LOG_FILE, mode="a",
                        header=not os.path.exists(LOG_FILE),
                        index=False
                    )

            time.sleep(0.02)

        print("[*] Cycle complete. Next scan in 60 seconds...\n")
        time.sleep(60)


# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    print("\n🎯  BREAKOUT TRIGGER SCANNER v3.8\n")

    while True:
        try:
            raw = input(
                "💰 Enter your trading capital ₹ (e.g. 500000): "
            ).strip()
            CAPITAL = float(
                raw.replace(",", "").replace("₹", "").strip()
            )
            if CAPITAL > 0:
                break
        except ValueError:
            pass
        print("   Please enter a valid number.")

    try:
        execute_live_monitoring_loop(CAPITAL)
    except KeyboardInterrupt:
        print("\n[-] Scanner terminated by user.")