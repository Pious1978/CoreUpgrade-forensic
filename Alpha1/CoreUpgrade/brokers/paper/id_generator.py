from abc import ABC, abstractmethod
import uuid

class OrderIdGenerator(ABC):
    @abstractmethod
    def generate_broker_order_id(self, prefix: str = "PAPER") -> str:
        pass

class StandardOrderIdGenerator(OrderIdGenerator):
    def generate_broker_order_id(self, prefix: str = "PAPER") -> str:
        return f"{prefix}-{uuid.uuid4().hex}"

class DeterministicOrderIdGenerator(OrderIdGenerator):
    def __init__(self, start_sequence: int = 1000):
        self._counter = start_sequence

    def generate_broker_order_id(self, prefix: str = "PAPER") -> str:
        self._counter += 1
        return f"{prefix}-ORD-{self._counter}"
