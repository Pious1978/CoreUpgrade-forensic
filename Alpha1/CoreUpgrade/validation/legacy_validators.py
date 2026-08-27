from contracts.broker.order_contract import OrderContract

class ExecutionValidator:
    """
    Final internal firewall ensuring order structural integrity 
    before hitting the gateway or external adapters.
    """
    @staticmethod
    def validate(order: OrderContract) -> None:
        if not order.order_id:
            raise ValueError("Missing order id in execution contract")
        if not order.correlation_id:
            raise ValueError("Missing correlation id for tracing")
        if not order.symbol:
            raise ValueError("Missing trading symbol")
        if not order.portfolio_id:
            raise ValueError("Missing portfolio identifier")
        if order.quantity <= 0:
            raise ValueError("Invalid order quantity: must be strictly positive")
