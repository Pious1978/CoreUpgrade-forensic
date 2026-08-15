# execution/certification/theorem_execution_intent_001.py
from execution.contracts.execution_intent import ExecutionIntent
from portfolio.contracts.portfolio_certificate import PortfolioCertificate

class ExecutionIntentAuthorizationTheorem:
    """
    THEOREM-EXECUTION-INTENT-001
    Invariant: An ExecutionIntent cannot be generated or dispatched to the OMS/EMS 
    unless its portfolio_certificate_hash explicitly matches a fully certified PortfolioCertificate.
    """
    id = "THEOREM-EXECUTION-INTENT-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls, 
        intent: ExecutionIntent, 
        portfolio_cert: PortfolioCertificate
    ) -> dict:
        
        # 1. Verify cryptographic binding to the certificate
        if intent.portfolio_certificate_hash != portfolio_cert.certificate_hash:
            return {
                "certified": False,
                "reason": "Execution Authorization Breach: Intent hash does not match PortfolioCertificate."
            }

        # 2. Verify that the underlying portfolio certificate itself passed all upstream gates
        if not portfolio_cert.certified:
            return {
                "certified": False,
                "reason": "Execution Authorization Breach: Attempted to trade an uncertified portfolio certificate."
            }

        # 3. Verify portfolio ID alignment
        if intent.portfolio_id != portfolio_cert.portfolio_id:
            return {
                "certified": False,
                "reason": "Execution Authorization Breach: Portfolio ID mismatch between intent and certificate."
            }

        return {
            "certified": True,
            "reason": "Execution intent successfully authorized by PortfolioCertificate lineage."
        }
