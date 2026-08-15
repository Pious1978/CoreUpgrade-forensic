class OrderStore:
    def __init__(self):
        self._orders = {}

    def append_state(self, order_id: str, response):
        if order_id not in self._orders:
            self._orders[order_id] = []
        self._orders[order_id].append(response)

    def get_history(self, order_id: str) -> list:
        return self._orders.get(order_id, [])

    def get_latest(self, order_id: str):
        history = self.get_history(order_id)
        return history[-1] if history else None
