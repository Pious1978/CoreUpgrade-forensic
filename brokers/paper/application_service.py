from decimal import Decimal
from typing import Optional, List, Tuple
from .contracts import ExecutionReportContract
from .policies import PolicyChain
from .factory import ExecutionResultFactory
from .configuration import BrokerConfiguration

class ExecutionApplicationService:
    def __init__(self, services, pipeline, snapshot_provider, policy_chain: Optional[PolicyChain] = None):
        self.services = services
        self.pipeline = pipeline
        self.snapshot_provider = snapshot_provider
        self.policy_chain = policy_chain or PolicyChain()

    def submit_order(self, order: OrderContract, config: BrokerConfiguration) -> ExecutionReportContract:
        timestamp: int = self.services.clock.now_ms()

        # 1. Policy Validation Chain
        valid, err_msg = self.policy_chain.validate(order, config.capabilities)
        if not valid:
            broker_order_id = self.services.id_generator.generate_broker_order_id(config.broker_name)
            outcome = ExecutionResultFactory.rejected(order, err_msg or "Policy chain failure", timestamp=timestamp)
            return self.services.commit_engine.commit_execution(order, broker_order_id, outcome, config.broker_name, order.correlation_id)

        # 2. Generate Broker Order ID
        broker_order_id: str = self.services.id_generator.generate_broker_order_id(config.broker_name)

        # 3. Create & Commit Submitted Report (Triggers EDA events)
        init_outcome = ExecutionResultFactory.submitted(order, timestamp=timestamp)
        self.services.commit_engine.commit_execution(order, broker_order_id, init_outcome, config.broker_name, order.correlation_id)

        # 4. Obtain Immutable Market Snapshot
        snapshot = self.snapshot_provider.get_snapshot(order.symbol)

        # 5. Execute Pipeline
        current_pos = self.services.position_engine.get_position(order.symbol)
        outcome = self.pipeline.process(order, current_pos, snapshot, self.services.clock)

        # 6 & 7. Commit Transaction & Publish Domain Events (Handled atomically inside CommitEngine)
        # 8. Return ExecutionReportContract
        return self.services.commit_engine.commit_execution(order, broker_order_id, outcome, config.broker_name, order.correlation_id)

    def cancel_order(self, client_order_id: str, config: BrokerConfiguration) -> ExecutionReportContract:
        timestamp: int = self.services.clock.now_ms()
        return self.services.commit_engine.commit_cancel(client_order_id, config.broker_name, timestamp)

    def get_order_status(self, client_order_id: str) -> Optional[ExecutionReportContract]:
        return self.services.query_service.get_order_status(client_order_id)

    def get_order_history(self, client_order_id: str) -> Tuple[ExecutionReportContract, ...]:
        return self.services.query_service.get_order_history(client_order_id)

    def get_positions(self) -> List[PositionContract]:
        return self.services.query_service.get_positions()

    def get_account_balance(self) -> AccountContract:
        return self.services.query_service.get_account_balance()
