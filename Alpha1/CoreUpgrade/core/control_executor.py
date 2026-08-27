from typing import Any
from core.control_definition import ControlDefinition
from core.audit_base import BaseAudit
from core.execution_context import ExecutionContext
from core.audit_artifact import AuditArtifact
from core.logger import get_logger

logger = get_logger("control_executor")


class ControlExecutor:
    """
    Explicit runtime binding engine connecting governance control definitions
    to individual audit execution modules.
    """

    def __init__(self, control: ControlDefinition, audit_instance: BaseAudit):
        self.control = control
        self.audit_instance = audit_instance

    def execute(self, context: ExecutionContext) -> AuditArtifact:
        logger.info(
            "Executing bound control module",
            extra={"control_id": self.control.control_id, "owner": self.control.owner_team}
        )

        if not self.audit_instance.validate(context):
            raise RuntimeError(f"Control validation failed for {self.control.control_id}")

        self.audit_instance.prepare(context)
        return self.audit_instance.run(context)
