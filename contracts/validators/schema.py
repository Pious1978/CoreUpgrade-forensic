"""
Schema Validator

Validates metadata mappings, payload schema structures, and mandatory domain fields 
before lineage sequence evaluation.
"""

from typing import Any, Mapping
from contracts.exceptions import ContractValidationError


def validate_contract_schema(contract: Any) -> None:
    """
    Validates metadata format and invokes concrete contract payload schema checks if present.
    Raises ContractValidationError if schema constraints fail.
    """
    if not isinstance(contract.metadata, Mapping):
        raise ContractValidationError("Schema validation failed: metadata must implement Mapping.")

    # Extension hook for domain-specific payload schema validation
    if hasattr(contract, "validate_payload_schema"):
        contract.validate_payload_schema()
