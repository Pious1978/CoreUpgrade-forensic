from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from core.audit_registry import AuditRegistry
from core.registry_validator import RegistryValidator
from core.dependency_graph import DependencyGraph
from core.audit_executor import AuditExecutor
from core.execution_context import ExecutionContext
from core.execution_scheduler import ExecutionScheduler, SchedulerConfig
from core.execution_manifest import ExecutionManifest
from core.artifact_store import ArtifactStore, LocalArtifactStore
from core.audit_result import AuditRunResult, compute_run_fingerprint
from core.audit_config import AuditConfig
from core.logger import get_logger

logger = get_logger("audit_suite")


class AuditSuite:
    """
    Institutional orchestration façade incorporating manifest capture,
    cryptographic fingerprinting, and centralized failure policies.
    """

    def __init__(
        self,
        config: Optional[AuditConfig] = None,
        scheduler_config: Optional[SchedulerConfig] = None,
        artifact_store: Optional[ArtifactStore] = None
    ):
        self.config = config or AuditConfig()
        self.scheduler_config = scheduler_config or SchedulerConfig()
        self.artifact_store = artifact_store or LocalArtifactStore()
        
        self.registry = AuditRegistry()
        self._bootstrap()

    def _bootstrap(self):
        logger.info("Bootstrapping AuditSuite control plane")
        validator = RegistryValidator(self.registry)
        validator.validate()
        self.dag = DependencyGraph(self.registry)
        self.executor = AuditExecutor(config=self.config)

    def before_run(self, context: ExecutionContext) -> None:
        logger.info("Executing before_run lifecycle hook", extra={"run_id": context.run_id})

    def after_run(self, result: AuditRunResult) -> None:
        logger.info("Executing after_run lifecycle hook", extra={"run_id": result.run_id, "status": result.status})

    def persist(self, result: AuditRunResult) -> str:
        return self.artifact_store.save(result)

    def run(self, custom_params: Optional[Dict[str, Any]] = None) -> AuditRunResult:
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.utcnow().isoformat()
        parameters = custom_params or {}
        
        context = ExecutionContext(
            run_id=run_id,
            parameters=parameters
        )

        self.before_run(context)
        logger.info("Starting audit suite execution run", extra={"run_id": run_id})

        manifest = ExecutionManifest.capture(
            run_id=run_id,
            registry_fingerprint=self.registry.get_fingerprint()
        )

        run_fingerprint = compute_run_fingerprint(
            registry_fingerprint=manifest.registry_fingerprint,
            git_commit=manifest.git_commit,
            config_environment=self.config.environment,
            parameters=parameters
        )

        scheduler = ExecutionScheduler(
            registry=self.registry,
            executor=self.executor,
            dag=self.dag,
            config=self.config,
            scheduler_config=self.scheduler_config
        )

        scheduler_result = scheduler.run(context)

        findings = []
        scores = {}
        failed_mapping = {}
        artifacts = {}

        for audit_id, artifact in scheduler_result.completed.items():
            artifacts[audit_id] = artifact
            if hasattr(artifact, "findings"):
                findings.extend(artifact.findings)
            if hasattr(artifact, "score"):
                scores[audit_id] = artifact.score

        for audit_id, err in scheduler_result.failed.items():
            failed_mapping[audit_id] = str(err)
            findings.append({
                "audit_id": audit_id,
                "severity": "CRITICAL",
                "message": str(err)
            })

        if failed_mapping and not scheduler_result.completed:
            status = "FAILED"
        elif failed_mapping:
            status = "PARTIAL"
        else:
            status = "SUCCESS"

        run_result = AuditRunResult(
            run_id=run_id,
            timestamp=timestamp,
            status=status,
            duration_seconds=scheduler_result.execution_time_seconds,
            audits_executed=len(scheduler_result.completed),
            manifest=manifest,
            run_fingerprint=run_fingerprint,
            findings=tuple(findings),
            scores=scores,
            artifacts=artifacts,
            failed_audits=failed_mapping
        )

        report_path = self.persist(run_result)
        object.__setattr__(run_result, 'report_path', report_path)

        self.after_run(run_result)

        logger.info(
            "Audit suite execution completed successfully",
            extra={
                "run_id": run_id,
                "status": status,
                "duration_seconds": scheduler_result.execution_time_seconds,
                "audits_executed": len(scheduler_result.completed),
                "failures": len(failed_mapping),
                "run_fingerprint": run_fingerprint,
                "storage_path": report_path
            }
        )

        return run_result
