"""
Identity Validator

Enforces that domain, contract type, and schema name constants match exactly 
between concrete domain classes and envelope metadata.
"""

from typing import Any
from contracts.exceptions import ContractValidationError


def validate_contract_identity(contract: Any) -> None:
    """
    Asserts that a contract's metadata matches its expected class identity constants.
    Raises ContractValidationError if a mismatch is detected.
    """
    expected_domain = getattr(contract, "DOMAIN", None)
    expected_type = getattr(contract, "CONTRACT_TYPE", None)
    expected_schema = getattr(contract, "SCHEMA_NAME", None)

    if expected_domain and contract.domain != expected_domain:
        raise ContractValidationError(
            f"Identity mismatch: domain '{contract.domain}' does not match expected '{expected_domain}'."
        )
    if expected_type and contract.contract_type != expected_type:
        raise ContractValidationError(
            f"Identity mismatch: contract_type '{contract.contract_type}' does not match expected '{expected_type}'."
        )
    if expected_schema and contract.schema_name != expected_schema:
        raise ContractValidationError(
            f"Identity mismatch: schema_name '{contract.schema_name}' does not match expected '{expected_schema}'."
        )
