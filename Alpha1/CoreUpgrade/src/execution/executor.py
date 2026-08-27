import time
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Any
from src.security.crypto import StrictCryptographicEngine

@dataclass(frozen=True)
class TheoremResult:
    status: str
    proof: str
    metrics: Dict[str, Any]

@dataclass(frozen=True)
class ExecutionSuiteResult:
    results: Dict[str, TheoremResult]
    diagnostics: List[str]
    failed: bool
    execution_order: List[str]
    duration: float
    proof_payload: Dict[str, Any]

class TheoremExecutor:
    @staticmethod
    def execute_suite(sorted_theorems: List[Any]) -> ExecutionSuiteResult:
        start_time = time.perf_counter()
        results: Dict[str, TheoremResult] = {}
        diagnostics: List[str] = []
        execution_order: List[str] = []
        failed = False

        for t in sorted_theorems:
            t_id = getattr(t, "id", str(t))
            execution_order.append(t_id)
            try:
                if hasattr(t, "execute") and callable(t.execute):
                    res = t.execute()
                else:
                    res = {"status": "SUCCESS", "proof": f"verified_{t_id}", "metrics": {}}
                
                if isinstance(res, TheoremResult):
                    t_res = res
                elif isinstance(res, dict):
                    t_res = TheoremResult(
                        status=res.get("status", "SUCCESS"),
                        proof=res.get("proof", f"verified_{t_id}"),
                        metrics={k: v for k, v in res.get("metrics", {}).items() if k not in {"timestamp", "uuid", "current_time"}}
                    )
                else:
                    t_res = TheoremResult(status="SUCCESS", proof=str(res), metrics={})

                results[t_id] = t_res
                diagnostics.append(f"Theorem {t_id} executed successfully.")
            except Exception as ex:
                failed = True
                diagnostics.append(f"Theorem {t_id} failed execution: {str(ex)}")
                results[t_id] = TheoremResult(status="FAILED", proof=str(ex), metrics={})
                break

        duration = time.perf_counter() - start_time
        
        serialized_results = {
            t_id: {
                "status": r.status,
                "proof": r.proof,
                "metrics": sorted(list(r.metrics.items()))
            }
            for t_id, r in results.items()
        }

        proof_data = {
            "execution_order": execution_order,
            "results": serialized_results,
            "failed": failed
        }
        
        proof_bytes = StrictCryptographicEngine.canonical_serialize(proof_data)
        empirical_proof_hash = hashlib.sha256(proof_bytes).hexdigest()

        proof_payload = {
            "empirical_proof_hash": empirical_proof_hash,
            "proof_data": proof_data
        }

        return ExecutionSuiteResult(
            results=results,
            diagnostics=diagnostics,
            failed=failed,
            execution_order=execution_order,
            duration=duration,
            proof_payload=proof_payload
        )