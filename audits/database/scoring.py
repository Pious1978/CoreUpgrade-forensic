import logging
import sys
from typing import Dict, Any

logger = logging.getLogger("DatabaseAudit")

CATEGORY_WEIGHTS = {
    "Integrity": 0.25,
    "Data Quality": 0.25,
    "Performance": 0.15,
    "Schema": 0.15,
    "Coverage": 0.10,
    "File Health": 0.10
}

class AuditContext:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {
            "timestamp": None,
            "pass": 0,
            "warning": 0,
            "fail": 0,
            "category_scores": {cat: {"pass": 0, "total": 0} for cat in CATEGORY_WEIGHTS},
            "details": []
        }

    def log_result(self, category: str, check_name: str, db_name: str, status: str, message: str):
        status_upper = status.upper()
        if status_upper == "PASS":
            self.results["pass"] += 1
        elif status_upper == "WARNING":
            self.results["warning"] += 1
        elif status_upper in ("FAIL", "CRITICAL"):
            self.results["fail"] += 1

        if category in self.results["category_scores"]:
            self.results["category_scores"][category]["total"] += 1
            if status_upper == "PASS":
                self.results["category_scores"][category]["pass"] += 1

        self.results["details"].append({
            "category": category,
            "check": check_name,
            "database": db_name,
            "status": status_upper,
            "message": message
        })
        logger.info(f"[{status_upper}] ({category}) {db_name} - {check_name}: {message}")

    def calculate_weighted_score(self) -> float:
        total_weighted_score = 0.0
        total_weight_applied = 0.0

        for cat, weight in CATEGORY_WEIGHTS.items():
            stats = self.results["category_scores"][cat]
            if stats["total"] > 0:
                cat_ratio = stats["pass"] / stats["total"]
                total_weighted_score += cat_ratio * weight
                total_weight_applied += weight

        if total_weight_applied == 0:
            return 0.0
        return round((total_weighted_score / total_weight_applied) * 100, 2)
