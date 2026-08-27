from typing import Protocol, TypeVar, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4
from contracts.research import ResearchSignalContract
from contracts.governance import ResearchApprovedContract
from contracts.portfolio import PortfolioIntentContract, PortfolioDecisionContract
from contracts.execution import ExecutionPlanContract, ExecutionResultContract
from contracts.learning import PerformanceFeedbackContract
from .policies import ResearchPromotionPolicy
from .strategies import EqualWeightAllocator, MaxWeightRiskPolicy, PositionSizer
from .broker import BrokerAdapter, PaperBroker
from .telemetry import PipelineTelemetry

@dataclass(frozen=True)
class PipelineContext:
    root_contract_id: UUID
    correlation_id: UUID
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

# --- Formal Stage Protocol ---
InT = TypeVar("InT", contravariant=True)
OutT = TypeVar("OutT", covariant=True)

class Stage(Protocol[InT, OutT]):
    def transform(self, data: InT) -> OutT:
        ...

@dataclass(frozen=True)
class PipelineResult:
    contracts: Tuple[Any, ...]
    telemetry: PipelineTelemetry


class ResearchGeneratorComponent:
    def transform(self, context: PipelineContext) -> ResearchSignalContract:
        return ResearchSignalContract(
            root_contract_id=context.root_contract_id,
            correlation_id=context.correlation_id,
            signal_id="sig-AAPL-2026-08",
            symbol="AAPL",
            suggested_weight=0.15,
            confidence_score=0.88
        )

class GovernanceComponent:
    def __init__(self, policy: ResearchPromotionPolicy = None):
        self.policy = policy or ResearchPromotionPolicy()

    def transform(self, signal: ResearchSignalContract) -> ResearchApprovedContract:
        if not self.policy.evaluate(signal.confidence_score):
            raise ValueError("Signal failed promotion confidence threshold.")
        return ResearchApprovedContract(
            parent_contract_id=signal.immutable_id,
            root_contract_id=signal.root_contract_id,
            correlation_id=signal.correlation_id,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            approved_weight=signal.suggested_weight,
            approval_reason=f"Passed confidence gate ({signal.confidence_score})."
        )

class PortfolioIntentComponent:
    def __init__(self, allocator: EqualWeightAllocator = None):
        self.allocator = allocator or EqualWeightAllocator()

    def transform(self, approved: ResearchApprovedContract) -> PortfolioIntentContract:
        return PortfolioIntentContract(
            parent_contract_id=approved.immutable_id,
            root_contract_id=approved.root_contract_id,
            correlation_id=approved.correlation_id,
            intent_id=f"intent-{approved.signal_id}",
            symbol=approved.symbol,
            target_weight=self.allocator.allocate(approved.approved_weight)
        )

class PortfolioRiskComponent:
    def __init__(self, risk_policy: MaxWeightRiskPolicy = None):
        self.risk_policy = risk_policy or MaxWeightRiskPolicy(max_cap=0.20)

    def transform(self, intent: PortfolioIntentContract) -> PortfolioDecisionContract:
        final_weight = self.risk_policy.apply(intent.target_weight)
        return PortfolioDecisionContract(
            parent_contract_id=intent.immutable_id,
            root_contract_id=intent.root_contract_id,
            correlation_id=intent.correlation_id,
            decision_id=f"decision-{intent.intent_id}",
            symbol=intent.symbol,
            approved_weight=final_weight,
            risk_score=0.08
        )

class ExecutionPlanningComponent:
    def __init__(self, sizer: PositionSizer = None):
        self.sizer = sizer or PositionSizer()

    def transform(self, decision: PortfolioDecisionContract) -> ExecutionPlanContract:
        target_qty = self.sizer.calculate_quantity(decision.approved_weight)
        return ExecutionPlanContract(
            parent_contract_id=decision.immutable_id,
            root_contract_id=decision.root_contract_id,
            correlation_id=decision.correlation_id,
            plan_id=f"plan-{decision.decision_id}",
            symbol=decision.symbol,
            target_quantity=target_qty,
            order_type="TWAP"
        )

class BrokerExecutionComponent:
    def __init__(self, broker: BrokerAdapter = None):
        self.broker = broker or PaperBroker()

    def transform(self, plan: ExecutionPlanContract) -> ExecutionResultContract:
        return self.broker.execute(plan)

class FeedbackComponent:
    def transform(self, result: ExecutionResultContract) -> PerformanceFeedbackContract:
        return PerformanceFeedbackContract(
            parent_contract_id=result.immutable_id,
            root_contract_id=result.root_contract_id,
            correlation_id=result.correlation_id,
            feedback_id=f"fb-{result.result_id}",
            symbol=result.symbol,
            expected_price=175.00,
            executed_price=result.average_fill_price,
            realized_pnl=1250.00
        )

class VSCPipeline:
    """
    VSC 1.1 Orchestrator with PipelineContext and PipelineTelemetry integration.
    """
    def __init__(
        self,
        research_gen: Stage[PipelineContext, ResearchSignalContract],
        governance: Stage[ResearchSignalContract, ResearchApprovedContract],
        intent_stage: Stage[ResearchApprovedContract, PortfolioIntentContract],
        risk_stage: Stage[PortfolioIntentContract, PortfolioDecisionContract],
        planning_stage: Stage[PortfolioDecisionContract, ExecutionPlanContract],
        broker_stage: Stage[ExecutionPlanContract, ExecutionResultContract],
        feedback_stage: Stage[ExecutionResultContract, PerformanceFeedbackContract]
    ):
        self.research_gen = research_gen
        self.governance = governance
        self.intent_stage = intent_stage
        self.risk_stage = risk_stage
        self.planning_stage = planning_stage
        self.broker_stage = broker_stage
        self.feedback_stage = feedback_stage
        self.telemetry = PipelineTelemetry()

    def _execute_stage(self, stage_name: str, stage_func, input_data: Any) -> Any:
        start_time = perf_counter()
        output_data = stage_func(input_data)
        duration_ms = (perf_counter() - start_time) * 1000.0
        
        self.telemetry.record(
            stage_name=stage_name,
            duration_ms=duration_ms,
            input_type=type(input_data).__name__,
            output_type=type(output_data).__name__
        )
        return output_data

    def run(self) -> PipelineResult:
        context = PipelineContext(
            root_contract_id=uuid4(),
            correlation_id=uuid4()
        )

        signal = self._execute_stage("Research", self.research_gen.transform, context)
        approved = self._execute_stage("Governance", self.governance.transform, signal)
        intent = self._execute_stage("Portfolio Intent", self.intent_stage.transform, approved)
        decision = self._execute_stage("Portfolio Risk", self.risk_stage.transform, intent)
        plan = self._execute_stage("Execution Planning", self.planning_stage.transform, decision)
        result = self._execute_stage("Broker Execution", self.broker_stage.transform, plan)
        feedback = self._execute_stage("Performance Feedback", self.feedback_stage.transform, result)

        contracts = (signal, approved, intent, decision, plan, result, feedback)
        return PipelineResult(contracts=contracts, telemetry=self.telemetry)
