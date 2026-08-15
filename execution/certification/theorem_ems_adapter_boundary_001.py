from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
# execution/certification/theorem_ems_adapter_boundary_001.py
from execution.contracts.ems_contract import EMSOrderRequest
from execution.contracts.broker_submission_contract import BrokerSubmissionResult

class EMSAdapterBoundaryTheorem(EmpiricalTheorem):
    """
    THEOREM-EMS-ADAPTER-BOUNDARY-001

    Invariant:
    Broker submission receipts must preserve
    the cryptographic lineage of the EMSOrderRequest.

    Adapter implementations may translate protocols,
    but cannot alter execution intent.
    """

    id = "THEOREM-EMS-ADAPTER-BOUNDARY-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        request: EMSOrderRequest,
        submission: BrokerSubmissionResult
    ) -> dict:

        if request.request_hash != submission.ems_request_hash:
            return {
                "certified": False,
                "reason": (
                    "EMS adapter boundary violation: "
                    "Broker receipt does not reference originating EMS request."
                ),
                "expected_hash": request.request_hash,
                "observed_hash": submission.ems_request_hash
            }

        if not submission.submission_id:
            return {
                "certified": False,
                "reason": (
                    "EMS adapter boundary violation: "
                    "Missing broker submission identifier."
                )
            }

        return {
            "certified": True,
            "reason": None
        }

