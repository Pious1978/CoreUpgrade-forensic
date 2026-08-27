from abc import ABC, abstractmethod
from contracts.execution import ExecutionPlanContract, ExecutionResultContract

class BrokerAdapter(ABC):
    @abstractmethod
    def execute(self, plan: ExecutionPlanContract) -> ExecutionResultContract:
        pass

class PaperBroker(BrokerAdapter):
    def execute(self, plan: ExecutionPlanContract) -> ExecutionResultContract:
        return ExecutionResultContract(
            parent_contract_id=plan.immutable_id,
            root_contract_id=plan.root_contract_id,
            correlation_id=plan.correlation_id,
            result_id=f"result-{plan.plan_id}",
            symbol=plan.symbol,
            executed_quantity=plan.target_quantity,
            average_fill_price=175.50,
            venue="PAPER_EXCHANGE",
            slippage=0.05,
            commission=1.50,
            latency_ms=15.0,
            fill_ratio=1.0,
            market_impact=0.0002
        )
