from typing import Tuple, Any
from ..exceptions import TransactionCommitError

class PromotionUnitOfWork:
    """Ensures transactional atomicity: commit all generated immutable contracts or rollback entirely."""
    
    def __init__(self) -> None:
        self._staged_contracts: list = []

    def stage(self, contract: Any) -> None:
        self._staged_contracts.append(contract)

    def commit(self) -> Tuple[Any, ...]:
        try:
            # Simulate atomic commit to append-only contract store / event bus
            persisted = tuple(self._staged_contracts)
            self._staged_contracts.clear()
            return persisted
        except Exception as e:
            self._staged_contracts.clear()
            raise TransactionCommitError(f"Failed to commit promotion transaction batch: {e}") from e

    def rollback(self) -> None:
        self._staged_contracts.clear()
