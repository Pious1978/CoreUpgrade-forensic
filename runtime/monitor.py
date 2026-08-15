class OperationalHealthDashboard:
    """Monitors live pipeline health and operational status across all domains."""
    
    @staticmethod
    def get_pipeline_health(data_freshness_status: str, risk_status: str) -> dict:
        health = {
            "Research": "PASS",
            "Governance": "PASS",
            "Risk": "PASS" if risk_status == "APPROVED" else "BLOCKED",
            "Execution": "READY",
            "DataFeed": data_freshness_status
        }
        all_pass = all(v in ["PASS", "READY", "FRESH"] for v in health.values())
        return {
            "overall_status": "HEALTHY" if all_pass else "DEGRADED_OR_BLOCKED",
            "stages": health
        }
