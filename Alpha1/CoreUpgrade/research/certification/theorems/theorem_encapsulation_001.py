# research/certification/theorems/theorem_encapsulation_001.py
from research.data.provenance_graph import FeatureNode
from research.governance.artifacts import ProofArtifact

class EncapsulationTheorem:
    id = "THEOREM-ENCAPSULATION-001"
    version = "1.0.0"
    
    @staticmethod
    def verify(signal_node: FeatureNode) -> ProofArtifact | None:
        """
        Invariant: Every feature participating in certification must originate 
        strictly from tracked provenance nodes.
        """
        visited = set()
        
        def dfs(node: FeatureNode, path: list):
            if node.node_hash in visited:
                return True, []
            visited.add(node.node_hash)
            current_path = path + [node]
            
            # The executable security boundary
            if node.operation in ("untracked_injection", "provenance_escaped"):
                return False, current_path
                
            for parent in node.parents:
                is_valid, error_path = dfs(parent, current_path)
                if not is_valid:
                    return False, error_path
            return True, []
            
        is_encapsulated, traceback = dfs(signal_node, [])
        if is_encapsulated:
            return None
            
        leak_node = traceback[-1]
        return ProofArtifact(
            theorem_id=EncapsulationTheorem.id,
            status="FAIL_THEOREM",
            failed_node=leak_node.name,
            operation=leak_node.operation,
            interval=(leak_node.domain.min_lag, leak_node.domain.max_lag),
            metadata=leak_node.metadata,
            violation="Untracked data escaped provenance graph (e.g., raw numpy injection).",
            trace_path=tuple(n.operation for n in reversed(traceback)),
            provenance_hash=leak_node.node_hash
        )
