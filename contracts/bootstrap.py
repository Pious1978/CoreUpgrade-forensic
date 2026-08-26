"""
Contract Bootstrap

Populates the ContractRegistry with all concrete domain contracts
and permanently freezes the registry to prevent runtime injection.
"""

from contracts.registry import ContractRegistry
from contracts.research.research_signal import ResearchSignalContract
from contracts.portfolio.portfolio_intent import PortfolioIntentContract
from contracts.execution import ExecutionPlanContract


def bootstrap_contract_system() -> None:
    """
    Registers core domain contracts and freezes the global ContractRegistry.
    """
    ContractRegistry.register(
        domain="research",
        schema_name="research_signal",
        schema_version="1.0",
        contract_cls=ResearchSignalContract,
    )

    ContractRegistry.register(
        domain="portfolio",
        schema_name="portfolio_intent",
        schema_version="1.0",
        contract_cls=PortfolioIntentContract,
    )

    ContractRegistry.register(
        domain="execution",
        schema_name="execution_plan",
        schema_version="1.0",
        contract_cls=ExecutionPlanContract,
    )

    # Lock down registry permanently post-bootstrap
    ContractRegistry.freeze()