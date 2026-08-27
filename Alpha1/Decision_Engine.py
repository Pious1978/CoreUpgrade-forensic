"""
Decision_Engine.py
-------------------------------------------------------------------------
Centralized Operational Decision Engine: Volatility-Adjusted Proximity (EMI)
Graduated Factor Realignment Framework (v7.3 Scanner Compliant)
"""
import numpy as np

class InstitutionalDecisionEngine:
    @staticmethod
    def process(results: dict) -> dict:
        """Calculates dynamic breakout windows, measurable deficits, and institutional tiers."""
        consolidation = results.get("Consolidation")
        rs_percentile = results.get("RS_Percentile", 50.0)
        current_price = results.get("Current_Price", 100.0)
        
        rs_accel = results.get("RS_Acceleration_Score", 65.0) 
        delivery_score = results.get("Delivery_Trend_Score", 70.0)
        
        sub_metrics = consolidation.metrics if consolidation else {}
        raw_range = float(sub_metrics.get("Raw_Range%", 10.0))
        raw_rvol = float(sub_metrics.get("Raw_RVOL", 1.0))
        
        # 1. RETRIEVE PIVOT AND VOLATILITY FEATURES
        atr_pct = results.get("ATR_Pct", 2.0)
        historical_pivot = results.get("Pivot_Price", current_price * 1.05)
        
        distance_to_pivot_pct = ((historical_pivot - current_price) / current_price) * 100.0
        if distance_to_pivot_pct < 0: distance_to_pivot_pct = 0.0

        # 2. EXPECTED MOVE INDEX (EMI): VOLATILITY-ADJUSTED DAYS TO PIVOT
        expected_days = distance_to_pivot_pct / (atr_pct + 1e-8)
        if expected_days <= 1.2:
            edp_label = "1 Trading Day"
        elif expected_days <= 3.0:
            edp_label = f"{int(np.ceil(expected_days))} Trading Days"
        else:
            edp_label = f"{int(np.ceil(expected_days))}–{int(np.ceil(expected_days * 1.5))} Days"

        # 3. COMPUTE DUAL SECTOR METRICS (RAW FLOAT VECTOR FOR TYPE-SAFE SORTING)
        opportunity_raw = ((rs_percentile * 0.40) + (rs_accel * 0.40) + (delivery_score * 0.20)) / 10.0
        readiness_raw = (consolidation.score if consolidation else 0.0) / 10.0

        # 4. INITIALIZE RE-ALIGNED LIFECYCLE ROUTINES
        lifecycle = "Tier 1 — Ready to Monitor Daily"
        deficit_msg = "None - Structurally Primed"
        actionable_trigger = f"🔥 ACTIVE TRIGGER - Buy breakout above ₹{round(historical_pivot, 1)} on Vol > 1.8x"

        # ---------------------------------------------------------------------
        # FIX 3: LOWER RS PERCENTILE FLOOR TO 50 FOR TIER 1 LOGIC
        # ---------------------------------------------------------------------
        if rs_percentile < 50.0:
            lifecycle = "Tier 3 — Weak RS"
            deficit_msg = f"RS = {round(rs_percentile, 1)} ( genuine laggard )"
            actionable_trigger = "WATCH - Structure ready. Execute only if theme activates or RS expands."
        elif rs_percentile < 60.0:
            lifecycle = "Tier 1 — Ready to Monitor Daily"
            deficit_msg = f"RS = {round(rs_percentile, 1)} (improving but below 60 — watch for leadership)"
            actionable_trigger = "WATCH - Good structure, RS needs to cross 60 before adding heavy sizing."
        
        # ---------------------------------------------------------------------
        # FIX 1: USE RANGE_TIER FROM SCANNER INSTEAD OF RAW 6% CUTOFF
        # ---------------------------------------------------------------------
        else:
            range_tier = results.get("Range_Tier", sub_metrics.get("Range_Tier", "WIDE"))
            
            # Fallback deduction rule if scanner structure drops raw column tokens
            if range_tier == "WIDE" and raw_range <= 6.0:
                range_tier = "COILED"

            if range_tier == "TIGHTENING":
                lifecycle = "Tier 1 — Ready to Monitor Daily"
                deficit_msg = f"Range tightening ({round(raw_range, 1)}%) — watching for coil"
                actionable_trigger = "WATCH - Structure tightening down smoothly. Monitor for final compression."
            elif range_tier == "FORMING" or raw_range > 10.0:
                lifecycle = "Tier 2 — Institutional Accumulation"
                deficit_msg = f"Range: {round(raw_range, 1)}% | Target: below 10%"
                actionable_trigger = "WATCH - Base is wide. Wait for VCP range contraction to downshift to tightening."

            # ---------------------------------------------------------------------
            # FIX 2: GRADUATED VOLUME THRESHOLDS INSTEAD OF BINARY 0.60
            # ---------------------------------------------------------------------
            if lifecycle != "Tier 2 — Institutional Accumulation":
                if raw_rvol <= 0.60:
                    deficit_msg = "None - Structurally Primed"
                    actionable_trigger = f"🔥 ACTIVE TRIGGER - Buy breakout above ₹{round(historical_pivot, 1)} on Vol > 1.8x"
                elif raw_rvol <= 0.85:
                    deficit_msg = f"Vol Ratio = {round(raw_rvol, 2)}x | Nearly dry — monitor daily"
                    actionable_trigger = "WATCH CLOSELY - One more session of dry-up needed"
                else:
                    lifecycle = "Tier 1 — Ready to Monitor Daily"
                    deficit_msg = f"Vol Ratio = {round(raw_rvol, 2)}x | Needs meaningful dry-up"
                    actionable_trigger = "WATCH - Await volume contraction below 0.85x"

        # Handle extreme structural damage overrides
        if rs_percentile < 40.0 or (consolidation and consolidation.score < 25.0):
            lifecycle = "❌ BROKEN / EXTENDED STRUCTURE"

        return {
            "Tier_Lifecycle": lifecycle,
            "Opportunity_Raw": round(opportunity_raw, 2),
            "Readiness_Raw": round(readiness_raw, 2),
            "Opportunity_Display": f"{round(opportunity_raw, 1)}/10",
            "Readiness_Display": f"{round(readiness_raw, 1)}/10",
            "Measurable_Deficit": deficit_msg,
            "Pivot_Dist": f"{round(distance_to_pivot_pct, 1)}%",
            "ATR_14d": f"{round(atr_pct, 2)}%",
            "EDP_Window": edp_label,
            "Actionable_Trigger": actionable_trigger
        }