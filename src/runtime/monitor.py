import hashlib
import marshal
from typing import List, Any

class RuntimeIntegrityMonitor:
    @staticmethod
    def compute_bytecode_hash(func_or_obj: Any) -> str:
        target = func_or_obj
        if not hasattr(target, "__code__") and hasattr(target, "execute"):
            target = target.execute
        
        if not hasattr(target, "__code__"):
            # Fallback if entirely unstructured.
            target_repr = str(type(target)) + str(id(target))
            return hashlib.sha256(target_repr.encode("utf-8")).hexdigest()

        code_obj = target.__code__
        
        # SEC-019: Use marshal for deterministic serialization of bytecode structures
        # Avoids non-deterministic object memory references.
        bytecode_payload = marshal.dumps(code_obj)
        return hashlib.sha256(bytecode_payload).hexdigest()

    @staticmethod
    def verify_runtime_integrity(theorems: List[Any], active_cert: Any) -> bool:
        if not active_cert or not hasattr(active_cert, "theorem_bytecode_hashes"):
            return False
        
        expected_hashes = active_cert.theorem_bytecode_hashes
        if not isinstance(expected_hashes, dict):
            return False

        try:
            for t in theorems:
                t_id = getattr(t, "id", None)
                if not t_id or t_id not in expected_hashes:
                    return False
                
                current_hash = RuntimeIntegrityMonitor.compute_bytecode_hash(t)
                expected_hash = expected_hashes[t_id]
                
                if current_hash != expected_hash:
                    return False
            return True
        except Exception:
            return False