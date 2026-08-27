from typing import Any
from datetime import datetime
from .execution_context import ExecutionContext
from contracts.events import DomainEvent, GovernanceActionType
from event_store.publisher import EventPublisherProtocol

class PortfolioControlPlane:
    def __init__(
        self,
        research: Any,
        portfolio: Any,
        risk: Any,
        execution_planner: Any,
        governance: Any,
        execution: Any,
        event_publisher: EventPublisherProtocol
    ):
        self.research = research
        self.portfolio = portfolio
        self.risk = risk
        self.execution_planner = execution_planner
        self.governance = governance
        self.execution = execution
        self.event_publisher = event_publisher
        self._sequence_counters = {}

    def run_cycle(self, context: ExecutionContext) -> Any:
        run_id = context.run_id
        if run_id not in self._sequence_counters:
            self._sequence_counters[run_id] = 0

        try:
            # 1. Research Candidates
            res_out = self.research.generate_candidates(context)
            res_fp = res_out.fingerprint()

            # 2. Portfolio Optimization
            port_out = self.portfolio.optimize(res_out, context)
            port_fp = port_out.fingerprint()
            self._emit(context, "research", "RESEARCH_DONE", res_fp, port_fp)

            # 3. Risk Verification
            risk_out = self.risk.evaluate(port_out, context)
            risk_fp = risk_out.fingerprint()
            self._emit(context, "portfolio", "OPTIMIZED", port_fp, risk_fp)

            # 4. Execution Planning
            exec_plan = self.execution_planner.plan(port_out, context)
            plan_fp = exec_plan.fingerprint()
            self._emit(context, "risk", "RISK_CHECKED", risk_fp, plan_fp)

            # 5. Governance Evaluation (Orthogonal Action Gate)
            gov_report = self.governance.evaluate(exec_plan, risk_out, context)
            gov_fp = gov_report.fingerprint()
            self._emit(context, "governance", "GOVERNANCE_EVALUATED", plan_fp, gov_fp)

            action = getattr(gov_report, "action", GovernanceActionType.ABORT)
            
            if action != GovernanceActionType.EXECUTE:
                self._emit(context, "governance", f"HALTED_{action.value}", gov_fp, gov_fp)
                return gov_report

            # 6. Execution Routing
            exec_result = self.execution.execute(exec_plan, context)
            exec_fp = exec_result.fingerprint()
            self._emit(context, "execution", "EXECUTED", gov_fp, exec_fp)

            return exec_result

        except Exception as e:
            raise RuntimeError(f"Pipeline failed for Run ID {run_id}: {e}") from e

    def _emit(self, context: ExecutionContext, domain: str, stage: str, in_fp: str, out_fp: str):
        seq = self._sequence_counters[context.run_id]
        self._sequence_counters[context.run_id] += 1

        event = DomainEvent(
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            sequence=seq,
            domain=domain,
            stage=stage,
            timestamp=datetime.utcnow(),
            input_fingerprint=in_fp,
            output_fingerprint=out_fp
        )
        self.event_publisher.publish(event)
