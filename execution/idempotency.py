class IdempotencyGuard:
    """
    Tracks processed order IDs to prevent duplicate transmissions 
    while safely supporting retry recovery after transmission failures.
    """
    def __init__(self):
        self._processed_orders = set()
        self._failed_attempts = set()

    def check(self, order_id: str, allow_retry: bool = False) -> None:
        if order_id in self._processed_orders:
            raise ValueError(f"Duplicate order submission detected. Order ID {order_id} has already been processed.")
        if allow_retry and order_id in self._failed_attempts:
            self._failed_attempts.remove(order_id)
        self._processed_orders.add(order_id)

    def record_failure(self, order_id: str) -> None:
        """Removes order from success set and flags it for potential retry recovery."""
        if order_id in self._processed_orders:
            self._processed_orders.remove(order_id)
        self._failed_attempts.add(order_id)

    def reset(self) -> None:
        self._processed_orders.clear()
        self._failed_attempts.clear()
