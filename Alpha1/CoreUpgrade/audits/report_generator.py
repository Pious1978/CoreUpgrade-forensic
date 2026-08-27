from typing import Mapping, Any, Dict, List
import json
from core.audit_result import AuditRunResult
from core.logger import get_logger

logger = get_logger("report_generator")


class ReportGenerator:
    """
    Institutional reporting engine that transforms immutable AuditRunResults
    into executive summaries, compliance metrics, and structured artifacts.
    """

    @staticmethod
    def generate_executive_summary(result: AuditRunResult) -> Dict[str, Any]:
        """Produces a high-level C-suite executive summary from an audit run result."""
        total_findings = len(result.findings)
        critical_count = sum(
            1 for f in result.findings 
            if str(f.get("severity", "")).upper() == "CRITICAL"
        )
        warning_count = sum(
            1 for f in result.findings 
            if str(f.get("severity", "")).upper() == "WARNING"
        )

        avg_score = (
            sum(result.scores.values()) / len(result.scores)
            if result.scores else 0.0
        )

        return {
            "run_id": result.run_id,
            "timestamp": result.timestamp,
            "status": result.status,
            "run_fingerprint": result.run_fingerprint,
            "environment": result.manifest.environment,
            "git_commit": result.manifest.git_commit,
            "duration_seconds": result.duration_seconds,
            "audits_executed": result.audits_executed,
            "failed_audits_count": len(result.failed_audits),
            "aggregate_score": round(avg_score, 2),
            "findings_breakdown": {
                "total": total_findings,
                "critical": critical_count,
                "warning": warning_count
            }
        }

    @staticmethod
    def generate_markdown_report(result: AuditRunResult) -> str:
        """Generates a formatted markdown executive report for compliance repositories."""
        summary = ReportGenerator.generate_executive_summary(result)
        
        md_lines = [
            f"# Institutional Audit Executive Report",
            f"**Run ID:** {summary['run_id']}  ",
            f"**Timestamp:** {summary['timestamp']}  ",
            f"**Status:** `{summary['status']}`  ",
            f"**Run Fingerprint:** `{summary['run_fingerprint']}`  ",
            f"**Environment:** {summary['environment']} (`{summary['git_commit']}`)  ",
            f"**Execution Duration:** {summary['duration_seconds']}s  ",
            f"**Aggregate Score:** {summary['aggregate_score']}/100.0  ",
            "",
            "## Summary Metrics",
            f"- **Audits Executed:** {summary['audits_executed']}",
            f"- **Failed Audits:** {summary['failed_audits_count']}",
            f"- **Total Findings:** {summary['findings_breakdown']['total']} (Critical: {summary['findings_breakdown']['critical']}, Warnings: {summary['findings_breakdown']['warning']})",
            "",
            "## Audit Scores",
        ]

        for audit_id, score in result.scores.items():
            md_lines.append(f"- **{audit_id}**: `{score}/100.0`")

        if result.failed_audits:
            md_lines.extend([
                "",
                "## Failed Infrastructure Blocks",
            ])
            for audit_id, err in result.failed_audits.items():
                md_lines.append(f"- **{audit_id}**: {err}")

        md_lines.extend([
            "",
            "---",
            "*Generated automatically by Institutional Audit Control Plane.*"
        ])

        return "\n".join(md_lines)
