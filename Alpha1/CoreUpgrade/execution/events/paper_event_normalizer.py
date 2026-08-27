from datetime import datetime
from decimal import Decimal

from execution.events.event_normalizer import AbstractEventNormalizer
from execution.contracts.event_gateway_contract import GatewayIngressPayload
from execution.contracts.execution_event import ExecutionEvent
from execution.events.normalization_result import EventNormalizationResult


class PaperExchangeEventNormalizer(AbstractEventNormalizer):

    @property
    def broker_name(self) -> str:
        return "PAPER_EXCHANGE"


    @property
    def version(self) -> str:
        return "1.0.0"


    def normalize(
        self,
        ingress: GatewayIngressPayload
    ) -> EventNormalizationResult:

        payload = ingress.raw_payload

        event = ExecutionEvent(
            event_id=payload["event_id"],
            order_id=payload["order_id"],
            intent_id=payload["intent_id"],
            event_type=payload["event_type"],
            fill_price=Decimal(payload["fill_price"])
                if payload.get("fill_price")
                else None,
            fill_quantity=Decimal(payload["fill_quantity"])
                if payload.get("fill_quantity")
                else None,
            remaining_quantity=Decimal(payload["remaining_quantity"])
                if payload.get("remaining_quantity")
                else None,
            timestamp=datetime.fromisoformat(
                payload["timestamp"]
            ),
            raw_message=str(payload)
        )

        return EventNormalizationResult(
            ingress_hash=ingress.ingress_hash,
            execution_event=event,
            normalizer_name=self.broker_name,
            normalizer_version=self.version
        )
