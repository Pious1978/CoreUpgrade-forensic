# portfolio/certification/theorems/theorem_constraint_001.py
from portfolio.contracts.portfolio_certificate import PortfolioCertificate
from portfolio.contracts.constraint_contract import ConstraintSet
from portfolio.construction.constraint_registry import VersionedConstraintRegistry

class ConstraintComplianceTheorem:
    id = "THEOREM-CONSTRAINT-001"
    version = "1.1.0" # Upgraded for fail-closed registry integration
    
    @classmethod
    def verify(cls, certificate: PortfolioCertificate, constraint_set: ConstraintSet) -> dict:
        """
        Invariant 1: Constraints hash must match certificate ruleset hash.
        Invariant 2: All HARD constraints must evaluate to 'PASS'.
        Invariant 3: Fail-closed if any evaluation is missing or corrupted.
        """
        if certificate.constraints_hash != constraint_set.ruleset_hash:
            return {
                "certified": False,
                "reason": "Constraint hash mismatch. Ruleset has been tampered with."
            }
            
        registry = VersionedConstraintRegistry()
        severity_map = {c.constraint_id: c.severity for c in constraint_set.constraints}
        evaluated_ids = {e.constraint_id for e in certificate.constraint_evaluations}
        
        # FAIL CLOSED: Ensure every declared constraint was actually evaluated
        for constraint in constraint_set.constraints:
            if constraint.constraint_id not in evaluated_ids:
                return {
                    "certified": False,
                    "reason": f"FAIL CLOSED: Constraint '{constraint.constraint_id}' was declared in ruleset but never evaluated."
                }
            
            # Verify the constraint type is known to the registry
            try:
                registry.get_evaluator(constraint.constraint_type)
            except KeyError as e:
                return {
                    "certified": False,
                    "reason": f"FAIL CLOSED: {str(e)}"
                }

        # Check severities and statuses
        for evaluation in certificate.constraint_evaluations:
            severity = severity_map.get(evaluation.constraint_id, "HARD") # Default to HARD safety
            
            if severity == "HARD" and evaluation.status == "FAIL":
                return {
                    "certified": False,
                    "reason": f"HARD constraint violation: {evaluation.constraint_id} (Observed: {evaluation.observed_value}, Limit: {evaluation.limit})"
                }
                
        return {"certified": True}
