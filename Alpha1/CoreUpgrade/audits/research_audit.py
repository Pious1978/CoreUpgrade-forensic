"""
audits/research_audit.py

Institutional-grade research audit module. Validates indicator reproducibility,
detects look-ahead bias via source inspection and timeline checks, checks for 
post-warmup NaN/infinite value leakage, verifies feature availability, and 
computes a quantitative Research Quality Score.
"""

import pandas as pd
import numpy as np
import inspect
from datetime import datetime
from typing import Dict, List, Any, Tuple, Callable, Optional

class ResearchAudit:
    def __init__(
        self, 
        df: pd.DataFrame, 
        indicator_func: Callable, 
        symbol: str, 
        warmup_period: int = 30,
        feature_timestamps: Optional[Dict[str, datetime]] = None,
        signal_date: Optional[datetime] = None,
        control_id: str = "CTRL_RESEARCH_INTEGRITY"
    ):
        """
        df: Processed dataframe with computed indicators and features.
        indicator_func: The deterministic function used to compute indicators.
        warmup_period: Number of initial rows expected to contain valid warm-up NaNs.
        feature_timestamps: Mapping of feature names to their actual publication/availability timestamps.
        signal_date: The specific target execution/decision timestamp.
        """
        self.df = df.copy()
        self.indicator_func = indicator_func
        self.symbol = symbol
        self.warmup_period = warmup_period
        self.feature_timestamps = feature_timestamps or {}
        self.signal_date = signal_date
        self.control_id = control_id
        self.findings: List[Dict[str, Any]] = []

    def run_audit(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        self.findings = []

        if self.df.empty:
            self._add_finding(
                finding_id="RES_ERR_001",
                severity="CRITICAL",
                title="Empty Research Dataset",
                description=f"Research dataset for {self.symbol} contains no records."
            )
            return self.findings, self._calculate_quality_score(reproducible=False)

        reproducible = self._check_reproducibility()
        self._check_look_ahead_bias_source()
        self._check_post_warmup_nan()
        self._check_nan_inf_leakage()
        self._check_feature_availability()

        quality_report = self._calculate_quality_score(reproducible=reproducible)
        return self.findings, quality_report

    def _add_finding(
        self, 
        finding_id: str, 
        severity: str, 
        title: str, 
        description: str, 
        evidence: dict = None,
        affected_ratio: float = 0.0
    ):
        self.findings.append({
            "finding_id": finding_id,
            "control_id": self.control_id,
            "severity": severity,
            "title": title,
            "description": description,
            "affected_ratio": affected_ratio,
            "evidence": evidence or {"symbol": self.symbol},
            "detected_at": datetime.utcnow().isoformat()
        })

    def _check_reproducibility(self) -> bool:
        """Verify that running the indicator function twice yields identical outputs."""
        try:
            run_1 = self.indicator_func(self.df.copy())
            run_2 = self.indicator_func(self.df.copy())
            
            if not run_1.equals(run_2):
                self._add_finding(
                    finding_id="RES_ERR_002",
                    severity="HIGH",
                    title="Non-Deterministic Research Output",
                    description=f"Indicator function for {self.symbol} produced non-identical outputs on separate runs."
                )
                return False
            return True
        except Exception as e:
            self._add_finding(
                finding_id="RES_ERR_003",
                severity="CRITICAL",
                title="Indicator Execution Failure",
                description=f"Exception raised during indicator computation: {str(e)}"
            )
            return False

    def _check_look_ahead_bias_source(self):
        """Inspect indicator function source code for negative shifts or future data leakage indicators."""
        try:
            source = inspect.getsource(self.indicator_func)
            if "shift(-" in source or ".shift(-" in source:
                self._add_finding(
                    finding_id="RES_ERR_005",
                    severity="CRITICAL",
                    title="Potential Look-Ahead Bias (Negative Shift)",
                    description=f"Negative shift detected in the source code of indicator function for {self.symbol}."
                )
        except (TypeError, OSError):
            # Built-in or compiled functions cannot be inspected via source code
            pass

    def _check_post_warmup_nan(self):
        """Detect unexpected NaNs appearing after the designated indicator warm-up window."""
        if len(self.df) <= self.warmup_period:
            return

        post_warmup_df = self.df.iloc[self.warmup_period:]
        numeric_cols = post_warmup_df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            nan_count = post_warmup_df[col].isna().sum()
            if nan_count > 0:
                ratio = nan_count / len(post_warmup_df)
                self._add_finding(
                    finding_id="RES_ERR_006",
                    severity="HIGH",
                    title="Post-Warmup NaN Leakage",
                    description=f"Column '{col}' contains {nan_count} unexpected NaN values after the warmup period.",
                    affected_ratio=ratio
                )

    def _check_nan_inf_leakage(self):
        """Detect infinite values across all numeric indicator columns."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        total_rows = len(self.df)

        for col in numeric_cols:
            inf_count = np.isinf(self.df[col]).sum()
            if inf_count > 0:
                ratio = inf_count / total_rows
                self._add_finding(
                    finding_id="RES_ERR_004",
                    severity="HIGH",
                    title="Infinite Values in Indicators",
                    description=f"Column '{col}' contains {inf_count} infinite values.",
                    affected_ratio=ratio
                )

    def _check_feature_availability(self):
        """Verify that no feature was published after the decision/signal timestamp."""
        if not self.signal_date:
            return

        for feature_name, pub_timestamp in self.feature_timestamps.items():
            if pub_timestamp > self.signal_date:
                self._add_finding(
                    finding_id="RES_ERR_007",
                    severity="CRITICAL",
                    title="Feature Availability Violation (Look-Ahead)",
                    description=f"Feature '{feature_name}' published at {pub_timestamp} was used for signal date {self.signal_date}."
                )

    def _calculate_quality_score(self, reproducible: bool) -> Dict[str, Any]:
        score = 100
        base_penalties = {
            "CRITICAL": 40,
            "HIGH": 20,
            "MEDIUM": 10,
            "LOW": 5
        }

        if not reproducible:
            score -= 30

        for finding in self.findings:
            sev = finding.get("severity", "LOW")
            ratio = finding.get("affected_ratio", 0.0)
            # Scale penalty by affected dataset ratio if applicable, with a minimum base weight
            penalty = base_penalties.get(sev, 5) * (max(ratio, 0.1))
            score -= penalty

        score = max(0, int(score))

        status = "HEALTHY"
        if score < 50 or not reproducible:
            status = "REJECTED"
        elif score < 75:
            status = "WARNING"

        return {
            "symbol": self.symbol,
            "research_quality_score": score,
            "status": status,
            "reproducible": reproducible,
            "total_findings": len(self.findings)
        }
