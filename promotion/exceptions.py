class PromotionError(Exception):
    """Base exception for all promotion failures."""
    pass

class SourceValidationError(PromotionError):
    """Raised when source contract fails validation."""
    pass

class CapabilityCheckError(PromotionError):
    """Raised when capability checks fail."""
    pass

class BusinessRuleViolationError(PromotionError):
    """Raised when business logic rules or thresholds fail."""
    pass

class LineageViolationError(PromotionError):
    """Raised when DAG lineage verification fails."""
    pass

class LifecycleTransitionError(PromotionError):
    """Raised when source state transition policies fail."""
    pass

class TargetValidationError(PromotionError):
    """Raised when newly created target contract fails validation."""
    pass

class RegistryFrozenError(PromotionError):
    """Raised when attempting to modify a frozen promotion graph."""
    pass

class TransactionCommitError(PromotionError):
    """Raised when unit-of-work persistence or commit fails."""
    pass

class PolicyViolationError(PromotionError):
    """Raised when a promotion policy evaluation fails."""
    pass

class LockAcquisitionError(PromotionError):
    """Raised when a concurrent promotion lock cannot be acquired."""
    pass

class CompatibilityError(PromotionError):
    """Raised when framework, API, or schema compatibility checks fail."""
    pass

class MigrationError(PromotionError):
    """Raised when contract version migration fails."""
    pass

class PolicyResolutionError(PromotionError):
    """Raised when a promotion policy cannot be resolved."""
    pass

class IdempotencyTransitionError(PromotionError):
    """Raised when an invalid idempotency state transition is attempted."""
    pass

class DependencyError(PromotionError):
    """Raised when dependency injection container resolution fails."""
    pass

# Security Exception Hierarchy
class SecurityError(PromotionError):
    """Base class for all security-related failures."""
    pass

class AuthenticationError(SecurityError):
    """Raised when authentication credentials or tokens are invalid."""
    pass

class AuthorizationError(SecurityError):
    """Raised when an actor attempts an unauthorized operation."""
    pass

class PermissionDeniedError(AuthorizationError):
    """Raised when explicit permission scopes are missing."""
    pass

# Structured Exception Hierarchy for Retries (Avoids built-in TimeoutError shadowing)
class RetryablePromotionError(PromotionError):
    """Base class for transient errors eligible for automated retry."""
    pass

class DatabaseDeadlock(RetryablePromotionError):
    """Raised on relational database deadlock collisions."""
    pass

class BrokerUnavailable(RetryablePromotionError):
    """Raised when down-stream execution brokers time out or drop connections."""
    pass

class OptimisticLockFailure(RetryablePromotionError):
    """Raised when concurrent contract mutations collide on hash state."""
    pass

class PromotionTimeoutError(RetryablePromotionError):
    """Raised when an operation exceeds allocated lease/network limits."""
    pass

class FatalPromotionError(PromotionError):
    """Raised for permanent errors that bypass retries and go directly to DLQ."""
    pass
