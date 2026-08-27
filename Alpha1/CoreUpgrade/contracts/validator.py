"""
Contract Validator

Performs cryptographic hash integrity checks on instantiated contract objects 
to verify they have not suffered tampering during transport or persistence.
"""

from contracts.base_contract import BaseContract
from contracts.exceptions import ContractValidationError, ContractIntegrityError


class ContractValidator:

    @staticmethod
    def validate(contract: BaseContract) -> None:
        """
        Validates the payload hash integrity of a contract.
        Raises ContractValidationError or ContractIntegrityError if tampering is detected.
        """
        if not isinstance(contract, BaseContract):
            raise ContractValidationError("Validation failed: object is not a BaseContract instance.")

        contract.assert_valid()
