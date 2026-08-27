"""
Contract Exceptions

Defines the specialized exception hierarchy for all contract operations,
enabling precise programmatic error handling across domain boundaries.
"""

class ContractError(Exception):
    """Base exception for all platform contract operations."""
    pass


class ContractValidationError(ContractError):
    """Raised when structural, type, or constraint validation fails on a contract."""
    pass


class ContractIntegrityError(ContractError):
    """Raised when cryptographic payload hash verification fails (tampering/corruption)."""
    pass


class ContractSerializationError(ContractError):
    """Raised when JSON parsing, formatting, or object reconstruction fails."""
    pass


class ContractRegistryError(ContractError):
    """Raised when contract schema registration or lookup fails."""
    pass
