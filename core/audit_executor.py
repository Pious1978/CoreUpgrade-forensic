from typing import Optional, Any
import time
import traceback

from core.audit_base import BaseAudit
from core.execution_context import ExecutionContext
from core.audit_artifact import AuditArtifact
from core.audit_config import AuditConfig
from core.exceptions import AuditExecutionError
from core.logger import get_logger

logger = get_logger("audit_executor")


class AuditExecutor:
    """
    Institutional execution engine ensuring clean separation between business findings
    and internal execution diagnostics (tracebacks).
    """

    def __init__(self, config: Optional[AuditConfig] = None):
        self.config = config or AuditConfig()

    def execute(self, audit: BaseAudit, context: ExecutionContext) -> AuditArtifact:
        audit_id = audit.metadata.audit_id
        start_time = time.perf_counter()
        
        logger.info("Executing audit module lifecycle", extra={"audit_id": audit_id, "run_id": context.run_id})

        findings_list = []
        metrics_dict = {}
        score = 100.0
        status = "SUCCESS"

        try:
            if not audit.validate(context):
                raise AuditExecutionError(f"Audit pre-execution validation failed for {audit_id}")

            audit.prepare(context)
            result_payload = audit.run(context)

            if isinstance(result_payload, dict):
                if "findings" in result_payload:
                    findings_list.extend(result_payload["findings"])
                if "score" in result_payload:
                    score = float(result_payload["score"])
                if "metrics" in result_payload:
                    metrics_dict.update(result_payload["metrics"])
            elif hasattr(result_payload, "findings"):
                findings_list.extend(result_payload.findings)

        except Exception as e:
            trace = traceback.format_exc()
            # Full traceback logged securely internally, NOT exposed in findings
            logger.error(f"Audit execution failed: {audit_id}", extra={"error": str(e), "trace": trace})
            
            status = "FAILED"
            score = 0.0
            findings_list.append({
                "audit_id": audit_id,
                "severity": "CRITICAL",
                "message": f"Audit execution failed: {str(e)}"
            })
            raise AuditExecutionError(f"Audit {audit_id} failed: {str(e)}") from e

        duration = time.perf_counter() - start_time

        return AuditArtifact(
            audit_id=audit_id,
            name=audit.metadata.name,
            status=status,
            score=score,
            duration_seconds=duration,
            findings=tuple(findings_list),
            metrics=metrics_dict,
            metadata={"run_id": context.run_id, "timestamp": time.time()}
        )
