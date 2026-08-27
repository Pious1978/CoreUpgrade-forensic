# portfolio/optimization/solvers/base_solver.py
from abc import ABC, abstractmethod
from portfolio.optimization.contracts.optimization_contract import (
    OptimizationRequest,
    OptimizationResult
)
from portfolio.optimization.contracts.solver_contract import SolverMetadata
from portfolio.optimization.engines.objective_engine import ObjectiveFunction
from portfolio.contracts.constraint_contract import ConstraintSet

class AbstractSolver(ABC):
    """
    Pure numerical solver boundary. 
    Accepts standardized math objects and returns raw OptimizationResults.
    Has zero visibility into asset master data, timestamps, or execution pipelines.
    """

    @property
    @abstractmethod
    def metadata(self) -> SolverMetadata:
        """Exposes the exact backend, version, and execution environment hash."""
        pass

    @abstractmethod
    def solve(
        self,
        request: OptimizationRequest,
        objective: ObjectiveFunction,
        constraints: ConstraintSet
    ) -> OptimizationResult:
        """
        Executes the optimization mathematics. 
        Must return status codes like 'INFEASIBLE' raw rather than masking them.
        """
        pass
