__version__ = "2.6.2"
FRAMEWORK_VERSION = "2.6.2"
API_VERSION = 2
SCHEMA_COMPATIBILITY = ">=2,<3"

from .base_promoter import BasePromotionService
from .engine import PromotionEngine
from .graph import PromotionGraph, PromotionEdge, default_registry, promotion
from .graph_validator import GraphValidator
from .factory import PromotionFactory, ServiceLifetime, ServiceDescriptor
from .policy_resolver import PolicyResolver
from .capability_registry import CapabilityRegistry
from .migration import ContractMigrationManager
from .feature_flags import PromotionFeatureFlagService
from .compensation import SagaManager, CompensationAction, SagaRollbackError, CompensationResult, CompensationStep
from .configuration import PromotionConfiguration
from .plugin_loader import PluginLoader
from .middleware import PromotionMiddleware, AsyncMiddlewarePipeline, ExceptionMiddleware, AuthenticationMiddleware, AuthorizationMiddleware

from .context import PromotionContext, PermissionsContext, RiskContext, PortfolioContext, ExecutionContext
from .result_types import PromotionResult
from .status import PromotionStatus
from .metadata import PromotionMetadata
from .trace import TraceTree, Span
from .events import PromotionDomainEvent, PromotionTrace
from .event_store import EventStore, StoredEvent
from .events.event_envelope import EventEnvelope
from .serializers.event_serializer import EventSerializer
from .fingerprint import ContractFingerprint, canonicalize
from .idempotency_types import IdempotencyStatus
from .idempotency import AbstractIdempotencyStore, InMemoryIdempotencyStore, validate_idempotency_transition

from .plan import PromotionExecutionPlan, ExecutionPlanBuilder

from .security.audit_identity import AuditIdentity
from .security.authorization import AuthorizationService
from .security.policy_enforcement import PolicyEnforcement as SecurityMiddleware

from .policies.base_policy import BasePromotionPolicy, PolicyEvaluationResult
from .policies.research_policy import ResearchPromotionPolicy

from .abstractions import PromotionLock, DeadLetterQueue, EventBus, MetricsCollector, Tracer, Logger, AuditPublisher
from .lock import InMemoryPromotionLock
from .dlq import InMemoryDeadLetterQueue
from .retry import RetryPolicy
from .health.checker import PromotionHealthChecker
from .health.probes import PromotionHealthReport, HealthProbe, GraphProbe, StorageProbe
from .bootstrap import initialize_promotions

from .persistence.transaction_manager import AbstractTransactionManager
from .persistence.repository import PromotionRepository
from .persistence.unit_of_work import AbstractUnitOfWork
from .persistence.postgres_uow import PostgresUnitOfWork
from .persistence.postgres_repository import PostgresRepository

from .exceptions import (
    PromotionError,
    SourceValidationError,
    CapabilityCheckError,
    BusinessRuleViolationError,
    LineageViolationError,
    LifecycleTransitionError,
    TargetValidationError,
    RegistryFrozenError,
    TransactionCommitError,
    PolicyViolationError,
    LockAcquisitionError,
    CompatibilityError,
    MigrationError,
    PolicyResolutionError,
    IdempotencyTransitionError,
    DependencyError,
    SecurityError,
    AuthenticationError,
    AuthorizationError,
    PermissionDeniedError,
    RetryablePromotionError,
    DatabaseDeadlock,
    BrokerUnavailable,
    OptimisticLockFailure,
    PromotionTimeoutError,
    FatalPromotionError,
)

__all__ = [
    "__version__",
    "FRAMEWORK_VERSION",
    "API_VERSION",
    "SCHEMA_COMPATIBILITY",
    "BasePromotionService",
    "PromotionEngine",
    "PromotionGraph",
    "PromotionEdge",
    "default_registry",
    "promotion",
    "GraphValidator",
    "PromotionFactory",
    "ServiceLifetime",
    "ServiceDescriptor",
    "PolicyResolver",
    "CapabilityRegistry",
    "ContractMigrationManager",
    "PromotionFeatureFlagService",
    "SagaManager",
    "CompensationAction",
    "SagaRollbackError",
    "CompensationResult",
    "CompensationStep",
    "PromotionConfiguration",
    "PluginLoader",
    "PromotionMiddleware",
    "AsyncMiddlewarePipeline",
    "ExceptionMiddleware",
    "AuthenticationMiddleware",
    "AuthorizationMiddleware",
    "PromotionContext",
    "PermissionsContext",
    "RiskContext",
    "PortfolioContext",
    "ExecutionContext",
    "PromotionResult",
    "PromotionStatus",
    "PromotionMetadata",
    "TraceTree",
    "Span",
    "PromotionDomainEvent",
    "PromotionTrace",
    "EventStore",
    "StoredEvent",
    "EventEnvelope",
    "EventSerializer",
    "ContractFingerprint",
    "canonicalize",
    "IdempotencyStatus",
    "AbstractIdempotencyStore",
    "InMemoryIdempotencyStore",
    "validate_idempotency_transition",
    "PromotionExecutionPlan",
    "ExecutionPlanBuilder",
    "AuditIdentity",
    "AuthorizationService",
    "SecurityMiddleware",
    "BasePromotionPolicy",
    "PolicyEvaluationResult",
    "ResearchPromotionPolicy",
    "PromotionLock",
    "DeadLetterQueue",
    "EventBus",
    "MetricsCollector",
    "Tracer",
    "Logger",
    "AuditPublisher",
    "InMemoryPromotionLock",
    "InMemoryDeadLetterQueue",
    "RetryPolicy",
    "PromotionHealthChecker",
    "PromotionHealthReport",
    "HealthProbe",
    "GraphProbe",
    "StorageProbe",
    "initialize_promotions",
    "AbstractTransactionManager",
    "PromotionRepository",
    "AbstractUnitOfWork",
    "PostgresUnitOfWork",
    "PostgresRepository",
    "PromotionError",
    "SourceValidationError",
    "CapabilityCheckError",
    "BusinessRuleViolationError",
    "LineageViolationError",
    "LifecycleTransitionError",
    "TargetValidationError",
    "RegistryFrozenError",
    "TransactionCommitError",
    "PolicyViolationError",
    "LockAcquisitionError",
    "CompatibilityError",
    "MigrationError",
    "PolicyResolutionError",
    "IdempotencyTransitionError",
    "DependencyError",
    "SecurityError",
    "AuthenticationError",
    "AuthorizationError",
    "PermissionDeniedError",
    "RetryablePromotionError",
    "DatabaseDeadlock",
    "BrokerUnavailable",
    "OptimisticLockFailure",
    "PromotionTimeoutError",
    "FatalPromotionError",
]
