class ContractValidationError(ValueError):
    """Raised automatically when a contract fails structural or business validation constraints."""
    def __init__(self, contract_name: str, errors: list[str]):
        self.contract_name = contract_name
        self.errors = errors
        error_msg = f"Contract validation failed for '{contract_name}': {', '.join(errors)}"
        super().__init__(error_msg)
