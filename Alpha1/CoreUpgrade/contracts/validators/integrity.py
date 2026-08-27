"""
Integrity Validator

Enforces cryptographic payload hash verification on sealed contracts using crypto utilities.
"""

from typing import Any
import hmac
from contracts.crypto import compute_canonical_hash
from contracts.exceptions import ContractIntegrityError


def validate_contract_integrity(contract: Any) -> None:
    """
    Verifies that the contract's payload_hash matches its recomputed canonical hash.
    Raises ContractIntegrityError if integrity check fails.
    """
    if not contract.payload_hash:
        return

    expected_hash = compute_canonical_hash(contract, hash_algorithm=contract.hash_algorithm)
    if not hmac.compare_digest(expected_hash.encode("utf-8"), contract.payload_hash.encode("utf-8")):
        raise ContractIntegrityError(
            f"Integrity check failed for contract {contract.contract_id}: payload altered or corrupted."
        )
