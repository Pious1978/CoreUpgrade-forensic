from typing import Dict, Callable, Any, Tuple
from .exceptions import MigrationError

class ContractMigrationManager:
    """Manages multi-version contract upgrade chains during promotion ingestion."""

    def __init__(self) -> None:
        self._migrations: Dict[Tuple[str, int, int], Callable[[Any], Any]] = {}

    def register(self, contract_type_name: str, from_version: int, to_version: int, migrator: Callable[[Any], Any]) -> None:
        self._migrations[(contract_type_name, from_version, to_version)] = migrator

    def migrate(self, contract: Any, target_version: int) -> Any:
        contract_name = getattr(contract, "CONTRACT_TYPE", type(contract).__name__)
        current_version = getattr(contract, "version", 1)

        while current_version < target_version:
            key = (contract_name, current_version, current_version + 1)
            if key not in self._migrations:
                raise MigrationError(f"No migration path found for '{contract_name}' from version {current_version} to {current_version + 1}.")
            migrator = self._migrations[key]
            contract = migrator(contract)
            current_version += 1
        return contract
