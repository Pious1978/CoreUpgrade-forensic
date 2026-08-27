from typing import Dict, List, Set, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
import time
from dataclasses import dataclass

from core.audit_registry import AuditRegistry
from core.dependency_graph import DependencyGraph, ExecutionLayer
from core.audit_executor import AuditExecutor
from core.execution_context import ExecutionContext
from core.audit_config import AuditConfig
from core.exceptions import AuditExecutionError
from core.logger import get_logger

logger = get_logger("execution_scheduler")


@dataclass(frozen=True)
class SchedulerConfig:
    max_workers: int = 4
    default_timeout_seconds: float = 300.0
    enable_critical_path_sorting: bool = True


@dataclass
class SchedulerResult:
    completed: Dict[str, Any]
    failed: Dict[str, Exception]
    execution_time_seconds: float
    layers_executed: int


class ExecutionScheduler:
    """Institutional execution scheduler governed by central AuditConfig failure policies."""

    def __init__(
        self,
        registry: AuditRegistry,
        executor: AuditExecutor,
        dag: DependencyGraph,
        config: Optional[AuditConfig] = None,
        scheduler_config: Optional[SchedulerConfig] = None
    ):
        self.registry = registry
        self.executor = executor
        self.dag = dag
        self.audit_config = config or AuditConfig()
        self.config = scheduler_config or SchedulerConfig()

    def run(self, context: ExecutionContext) -> SchedulerResult:
        start_time = time.perf_counter()
        layers = self.dag.build_execution_layers()
        
        completed_audits: Set[str] = set()
        completed_results: Dict[str, Any] = {}
        failed_audits: Dict[str, Exception] = {}

        logger.info(
            "Starting execution scheduler",
            extra={"total_layers": len(layers), "max_workers": self.config.max_workers}
        )

        for layer in layers:
            if context.is_cancelled():
                logger.warning("Execution cancelled before layer processing", extra={"layer": layer.depth})
                break

            layer_result = self._execute_layer(layer, context, completed_audits)
            
            completed_results.update(layer_result.completed)
            failed_audits.update(layer_result.failed)
            completed_audits.update(layer_result.completed.keys())

            if layer_result.failed and not self._should_continue_on_failure(layer_result.failed):
                logger.error("Halting execution due to critical/blocking failures in layer", extra={"layer": layer.depth})
                break

        total_time = time.perf_counter() - start_time

        return SchedulerResult(
            completed=completed_results,
            failed=failed_audits,
            execution_time_seconds=total_time,
            layers_executed=len(layers)
        )

    def _execute_layer(
        self,
        layer: ExecutionLayer,
        context: ExecutionContext,
        completed: Set[str]
    ) -> SchedulerResult:
        layer_completed: Dict[str, Any] = {}
        layer_failed: Dict[str, Exception] = {}

        audit_ids = list(layer.audit_ids)
        if self.config.enable_critical_path_sorting:
            audit_ids = self._sort_by_criticality(audit_ids)

        logger.info("Executing layer batch", extra={"depth": layer.depth, "audits": audit_ids})

        with ThreadPoolExecutor(max_workers=min(len(audit_ids), self.config.max_workers)) as pool:
            future_to_audit = {
                pool.submit(self._run_single_audit, audit_id, context): audit_id
                for audit_id in audit_ids
            }

            done, not_done = wait(
                future_to_audit.keys(),
                timeout=self.config.default_timeout_seconds,
                return_when=ALL_COMPLETED
            )

            for future in done:
                audit_id = future_to_audit[future]
                try:
                    result = future.result()
                    layer_completed[audit_id] = result
                except Exception as e:
                    logger.error(f"Audit failed: {audit_id}", extra={"error": str(e)})
                    layer_failed[audit_id] = e

            for future in not_done:
                audit_id = future_to_audit[future]
                logger.error(f"Audit execution timed out and was cancelled: {audit_id}", extra={"timeout": self.config.default_timeout_seconds})
                future.cancel()
                layer_failed[audit_id] = AuditExecutionError(
                    f"Audit {audit_id} timed out after {self.config.default_timeout_seconds}s"
                )

        return SchedulerResult(
            completed=layer_completed,
            failed=layer_failed,
            execution_time_seconds=0.0,
            layers_executed=1
        )

    def _run_single_audit(self, audit_id: str, context: ExecutionContext) -> Any:
        audit_instance = self.registry.load(audit_id)
        return self.executor.execute(audit_instance, context)

    def _sort_by_criticality(self, audit_ids: List[str]) -> List[str]:
        def criticality_score(audit_id: str) -> Tuple[int, int]:
            metadata = self.registry.describe(audit_id)
            is_critical = 0 if getattr(metadata, "critical", True) else 1
            dependents_count = len(self.dag.dependents_of(audit_id))
            return (is_critical, -dependents_count)

        return sorted(audit_ids, key=criticality_score)

    def _should_continue_on_failure(self, failed_audits: Dict[str, Exception]) -> bool:
        policy = self.audit_config.failure_policy
        if not policy.fail_fast:
            return True

        for audit_id in failed_audits:
            try:
                metadata = self.registry.describe(audit_id)
                category = getattr(metadata, "category", "").lower()
                if category in policy.blocking_categories:
                    logger.error(f"Blocking failure category encountered: {category} in audit {audit_id}")
                    return False
            except Exception:
                return False

        return True
