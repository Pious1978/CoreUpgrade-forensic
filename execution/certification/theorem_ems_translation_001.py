from execution.certification.contracts.empirical_theorem import EmpiricalTheorem
# execution/certification/theorem_ems_translation_001.py
from execution.contracts.ems_contract import EMSOrderRequest
from execution.oms.order_manager import OrderRecord

class EMSTranslationTheorem(EmpiricalTheorem):
    """
    THEOREM-EMS-TRANSLATION-001

    Invariant:
    EMS translation may change representation,
    but must preserve the authorized OMS order intent.

    No quantity, side, instrument, price, or exchange mutation is permitted.
    """

    id = "THEOREM-EMS-TRANSLATION-001"
    version = "1.0.0"

    @classmethod
    def verify(
        cls,
        order_record: OrderRecord,
        ems_request: EMSOrderRequest
    ) -> dict:

        checks = {
            "order_id": (
                order_record.order_id ==
                ems_request.order_id
            ),
            "portfolio_id": (
                order_record.portfolio_id ==
                ems_request.portfolio_id
            ),
            "instrument_id": (
                order_record.instrument_id ==
                ems_request.instrument_id
            ),
            "side": (
                order_record.side ==
                ems_request.side
            ),
            "quantity": (
                order_record.quantity ==
                ems_request.quantity
            ),
            "order_type": (
                order_record.order_type ==
                ems_request.order_type
            ),
            "limit_price": (
                order_record.limit_price ==
                ems_request.limit_price
            ),
            "exchange": (
                order_record.exchange ==
                ems_request.exchange
            )
        }

        if not all(checks.values()):
            return {
                "certified": False,
                "reason": "EMS translation mutated authorized order attributes.",
                "failed_checks": [
                    key for key, value in checks.items()
                    if not value
                ]
            }

        return {
            "certified": True,
            "reason": None
        }

