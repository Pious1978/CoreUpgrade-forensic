from contracts.broker.order_contract import OrderContract
from contracts.broker.broker_response_contract import BrokerResponseContract

class BrokerResponseValidator:
    """
    Guards internal state from rogue adapter responses (overfills, mismatched IDs).
    """
    @staticmethod
    def validate(order: OrderContract, response: BrokerResponseContract) -> None:
        if response.order_id != order.order_id:
            raise ValueError(f"Broker response order_id mismatch: expected {order.order_id}, got {response.order_id}")
        
        if response.filled_quantity > order.quantity:
            raise ValueError(f"Overfill detected: filled quantity {response.filled_quantity} exceeds planned quantity {order.quantity}")
        
        if response.remaining_quantity < 0:
            raise ValueError("Broker response error: remaining quantity cannot be negative")
