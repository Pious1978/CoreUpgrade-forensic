from typing import Tuple, Any
from .unit_of_work import AbstractUnitOfWork
from .transaction_manager import AbstractTransactionManager

class PostgresUnitOfWork(AbstractUnitOfWork):
    def __init__(self, tx_manager: AbstractTransactionManager) -> None:
        self.tx_manager = tx_manager
        self._staged_contracts = []
        self._staged_events = []
        self._staged_audits = []
        self._staged_metrics = []

    def stage_contract(self, contract: Any) -> None:
        self._staged_contracts.append(contract)

    def stage_event(self, event: Any) -> None:
        self._staged_events.append(event)

    def stage_audit(self, audit: Any) -> None:
        self._staged_audits.append(audit)

    def stage_metric(self, metric: Any) -> None:
        self._staged_metrics.append(metric)

    def commit(self) -> Tuple[Any, ...]:
        self.tx_manager.begin()
        try:
            all_staged = tuple(self._staged_contracts + self._staged_events + self._staged_audits + self._staged_metrics)
            self.tx_manager.commit()
            self._clear()
            return all_staged
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        self.tx_manager.rollback()
        self._clear()

    def _clear(self) -> None:
        self._staged_contracts.clear()
        self._staged_events.clear()
        self._staged_audits.clear()
        self._staged_metrics.clear()
