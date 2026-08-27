"""
Consolidation_Scanner.py (Version 2.5 Smooth Curve Core)
"""
import numpy as np
from Standard_Engine_Types import FeatureStore, EngineResult

VERSION = "4.2.5_Smooth_Gaussian"

def evaluate(store: FeatureStore) -> EngineResult:
    """Evaluates chart attributes using continuous quadratic decay curves."""
    f = store.metrics
    
    range_20 = f.get("range_compression_20", 25.0)
    rvol = f.get("rvol", 2.0)
    sma50_dist = f.get("sma50_dist", -0.5)

    # 1. CONTINUOUS VOLATILITY COMPRESSION SUB-SCORE (Max 40 Points)
    # Uses a smooth exponential decay curve if the range expands past 4%
    if range_20 <= 4.0:
        vcp_sub = 40.0
    else:
        vcp_sub = 40.0 * np.exp(-((range_20 - 4.0) / 6.0) ** 2)

    # 2. CONTINUOUS VOLUME DRY-UP SUB-SCORE (Max 30 Points)
    # Smooth exponential decay curve for volume expansions past 0.4x average
    if rvol <= 0.4:
        vdu_sub = 30.0
    else:
        vdu_sub = 30.0 * np.exp(-((rvol - 0.4) / 0.5) ** 2)

    # 3. CONTINUOUS TREND ANCHOR ALIGNMENT SUB-SCORE (Max 30 Points)
    # Peak score is centered precisely at a 1% minor premium above the 50 DMA
    # Dips smoothly on either side using a localized Gaussian distribution
    trend_sub = 30.0 * np.exp(-((sma50_dist - 0.01) / 0.04) ** 2)

    total_setup_score = vcp_sub + vdu_sub + trend_sub
    
    # Engine self-confidence is based on how closely the sub-components align
    engine_confidence = (vcp_sub / 40.0) * 0.4 + (vdu_sub / 30.0) * 0.4 + (trend_sub / 30.0) * 0.2

    diagnostic_metrics = {
        "VCP_SubScore": round(float(vcp_sub), 1),
        "VDU_SubScore": round(float(vdu_sub), 1),
        "Trend_SubScore": round(float(trend_sub), 1),
        "Raw_Range%": round(range_20, 2),
        "Raw_RVOL": round(rvol, 2),
        "Raw_DMA50_Dist%": round(sma50_dist * 100, 2)
    }

    verdict = "PASS" if total_setup_score >= 70.0 else "WATCH" if total_setup_score >= 35.0 else "FAIL"

    return EngineResult(
        engine_name="Consolidation", version=VERSION,
        score=round(float(total_setup_score), 1), verdict=verdict,
        confidence=round(float(engine_confidence), 2), metrics=diagnostic_metrics,
        commentary=f"Trend:{diagnostic_metrics['Trend_SubScore']}/30, VCP:{diagnostic_metrics['VCP_SubScore']}/40, VDU:{diagnostic_metrics['VDU_SubScore']}/30"
    )