"""
core/factor_registry.py
-------------------------------------------------------------------------
Centralized factor registry defining economic signal families, weights,
and robust production-grade validation immune to python -O optimization.
"""

SIGNAL_FAMILIES = {
    "relative_strength": {"weight": 0.30},
    "institutional":     {"weight": 0.20},
    "structure":         {"weight": 0.20},
    "confirmation":      {"weight": 0.15},
    "risk_liquidity":    {"weight": 0.15},
}

FACTOR_DEFINITIONS = {
    # Relative Strength & Leadership (30%)
    "rs_percentile":      {"family": "relative_strength", "weight": 0.15, "owner": "RS_Engine"},
    "rs_acceleration":    {"family": "relative_strength", "weight": 0.08, "owner": "RS_Engine"},
    "momentum_score":     {"family": "relative_strength", "weight": 0.07, "owner": "Hybrid_Alpha"},

    # Institutional Activity (20%)
    "delivery_score":     {"family": "institutional",     "weight": 0.12, "owner": "RS_Engine"},
    "accumulation_ratio": {"family": "institutional",     "weight": 0.08, "owner": "Emerging_Leader"},

    # Technical Structure (20%)
    # reversal_exhaustion_score added here: a genuinely new pattern
    # type identified against real swing-trading methodology - every
    # other scanner in this system (Consolidation, Hybrid_Alpha,
    # Emerging_Leader, Earnings_Gap, Cup_and_Handle) is continuation-
    # only, none detect a stock reversing OUT of a downtrend. Same
    # treatment as earnings_gap_strength: small, conservative,
    # EXPLICITLY UNVALIDATED weight, taken from the 3 existing
    # structure factors (0.01 each), family total unchanged at 0.20.
    "trend_alignment":        {"family": "structure",         "weight": 0.07, "owner": "Hybrid_Alpha"},
    "base_compression":       {"family": "structure",         "weight": 0.06, "owner": "Consolidation"},
    "cup_handle_quality":     {"family": "structure",         "weight": 0.04, "owner": "Cup_Handle"},
    "reversal_exhaustion_score": {"family": "structure",      "weight": 0.03, "owner": "Reversal_Exhaustion"},

    # Breakout Confirmation (15%) — used only in execution mode
    # earnings_gap_strength added here: confirmed genuinely dead code
    # for months (Earnings_Gap_Scanner.py computed it, but it was never
    # in this registry, so Master_Terminal.py's scoring loop - which
    # iterates FACTOR_DEFINITIONS.items(), not scanner_factors' actual
    # distinct names - never even looked at it). Reframed as directly
    # relevant after comparing this system against real swing-trading
    # methodology: gap-up + volume confirmation is a named, recognized
    # entry signal there, not an arbitrary formula. Weight (0.03) is a
    # deliberately small, conservative, EXPLICITLY UNVALIDATED starting
    # point - taken by reducing the 3 existing confirmation factors by
    # 0.01 each, keeping the family's total exactly unchanged at 0.15.
    # Revisit once real backtest evidence exists, matching this
    # project's established "don't hardcode without validation"
    # principle from tonight's RS redesign work.
    "intraday_rvol":         {"family": "confirmation",      "weight": 0.05, "owner": "Breakout_Trigger"},
    "weekly_rvol":           {"family": "confirmation",      "weight": 0.04, "owner": "Breakout_Trigger"},
    "pivot_extension":       {"family": "confirmation",      "weight": 0.03, "owner": "Breakout_Trigger"},
    "earnings_gap_strength": {"family": "confirmation",      "weight": 0.03, "owner": "Earnings_Gap"},

    # Risk & Liquidity (15%)
    "liquidity_flow":     {"family": "risk_liquidity",    "weight": 0.08, "owner": "Hybrid_Alpha"},
    "volatility_score":   {"family": "risk_liquidity",    "weight": 0.07, "owner": "Consolidation"},
}

# ── Production-Grade Validation (Un-skippable) ───────────────────────────
for name, factor in FACTOR_DEFINITIONS.items():
    w = factor["weight"]
    if w <= 0:
        raise ValueError(f"Factor '{name}' weight must be > 0 (got {w})")
    if w > 1:
        raise ValueError(f"Factor '{name}' weight cannot exceed 1 (got {w})")

_total = sum(f["weight"] for f in FACTOR_DEFINITIONS.values())
if abs(_total - 1.0) > 1e-6:
    raise ValueError(f"Factor weights sum to {_total:.6f}; expected exactly 1.000000")

_family_totals = {}
for f in FACTOR_DEFINITIONS.values():
    _family_totals[f["family"]] = _family_totals.get(f["family"], 0) + f["weight"]

for family, total in _family_totals.items():
    expected = SIGNAL_FAMILIES[family]["weight"]
    if abs(total - expected) > 1e-6:
        raise ValueError(f"Family '{family}' factors sum to {total:.6f}, expected {expected:.6f}")