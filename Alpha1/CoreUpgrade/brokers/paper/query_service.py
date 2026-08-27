from typing import List, Tuple, Optional
from .contracts import ExecutionReportContract

class ExecutionQueryService:
    def __init__(self, repository, position_engine, account_engine):
        self.repository = repository
        self.position_engine = position_engine
        self.account_engine = account_engine

    def get_order_status(self, client_order_id: str) -> Optional[ExecutionReportContract]:
        return self.repository.get_latest(client_order_id)

    def get_order_history(self, client_order_id: str) -> Tuple[ExecutionReportContract, ...]:
        return self.repository.get_history(client_order_id)

    def get_positions(self) -> List[PositionContract]:
        return self.position_engine.get_all_positions()

    def get_account_balance(self) -> AccountContract:
        return self.account_engine.get_account_contract()
