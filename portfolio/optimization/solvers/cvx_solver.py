# portfolio/optimization/solvers/cvx_solver.py
import platform
import hashlib
from decimal import Decimal
from typing import Tuple
import cvxpy as cp
import numpy as np
import scipy

from portfolio.optimization.solvers.base_solver import AbstractSolver
from portfolio.optimization.contracts.solver_contract import SolverMetadata
from portfolio.optimization.contracts.optimization_contract import (
    OptimizationRequest,
    OptimizationResult
)
from portfolio.contracts.portfolio_certificate import TargetWeight

class CVXSolver(AbstractSolver):
    """
    CVXPY numerical backend adapter.
    Converts ObjectiveFunction and ConstraintSet into a CVXPY problem,
    executes the solver, and packages raw results into an OptimizationResult.
    """

    VERSION = "1.0.0"

    @property
    def metadata(self) -> SolverMetadata:
        return SolverMetadata(
            solver_name="CVXPY",
            solver_version=cp.__version__,
            backend="CVXPY",
            numerical_precision="float64",
            environment_hash=self._environment_hash()
        )

    def _environment_hash(self) -> str:
        """
        Binds core linear algebra runtime versions to ensure exact reproducibility across migrations.
        """
        env_payload = (
            f"python:{platform.python_version()}|"
            f"numpy:{np.__version__}|"
            f"scipy:{scipy.__version__}|"
            f"cvxpy:{cp.__version__}"
        )
        return hashlib.sha256(env_payload.encode('utf-8')).hexdigest()

    def solve(
        self,
        request: OptimizationRequest,
        objective,
        constraints
    ) -> OptimizationResult:
        """
        Executes the optimization problem via CVXPY.
        Does not mask solver failures or silently modify weights.
        """
        # Compile the abstract objective and constraints into a CVXPY problem
        problem = self._compile_problem(objective, constraints)
        
        # Execute the numerical solver backend
        problem.solve()

        status = problem.status

        # Standardize convergence states
        if status == cp.OPTIMAL:
            convergence = "OPTIMAL"
        elif status == cp.INFEASIBLE:
            convergence = "INFEASIBLE"
        elif status == cp.UNBOUNDED:
            convergence = "UNBOUNDED"
        else:
            convergence = str(status).upper()

        # Extract weights safely if optimal, otherwise empty tuple
        weights = self._extract_weights(problem) if convergence == "OPTIMAL" else tuple()

        # Gather solver iteration stats safely
        solver_stats = getattr(problem, "solver_stats", None)
        num_iters = getattr(solver_stats, "num_iters", -1) if solver_stats else -1

        return OptimizationResult(
            request_hash=request.request_hash,
            target_weights=weights,
            objective_value=Decimal(str(problem.value))
                if problem.value is not None and not np.isnan(problem.value)
                else Decimal("0"),
            solver_name=self.metadata.solver_name,
            solver_version=self.metadata.solver_version,
            iterations=num_iters,
            convergence_status=convergence
        )

    def _compile_problem(self, objective, constraints) -> cp.Problem:
        """
        Extension point for objective and constraint compilers 
        (e.g., Mean-Variance, Risk Parity).
        """
        raise NotImplementedError(
            "Concrete problem compilation delegate must be implemented "
            "by objective/constraint translation modules."
        )

    def _extract_weights(self, problem: cp.Problem) -> Tuple[TargetWeight, ...]:
        """
        Extracts decision variable values from a solved CVXPY problem 
        and coerces them into immutable TargetWeight decimal objects.
        """
        raise NotImplementedError(
            "Weight extraction logic pending decision variable mapping."
        )
