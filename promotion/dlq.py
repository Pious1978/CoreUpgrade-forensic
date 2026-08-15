from typing import List, Tuple, Any
from .abstractions import DeadLetterQueue

class InMemoryDeadLetterQueue(DeadLetterQueue):
    def __init__(self) -> None:
        self._queue: List[Tuple[Any, str, Any]] = []

    def push(self, source_contract: Any, reason: str, metadata: Any) -> None:
        self._queue.append((source_contract, reason, metadata))

    def get_all(self) -> List[Tuple[Any, str, Any]]:
        return list(self._queue)
