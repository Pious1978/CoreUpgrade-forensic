"""
Contract Rebuilder

Provides safe, polymorphic reconstruction of immutable contracts 
during state mutations and lifecycle transitions.
"""

from typing import Any, Dict


class ContractRebuilder:

    @staticmethod
    def rebuild(contract: Any, updates: Dict[str, Any]) -> Any:
        """
        Extracts dictionary representation, applies updates, and reconstructs 
        the exact concrete contract class using from_dict().
        """
        data = contract.to_dict(include_hash=False)
        data.update(updates)
        
        if not hasattr(contract.__class__, "from_dict"):
            raise TypeError(f"Contract class '{contract.__class__.__name__}' does not implement 'from_dict'.")
            
        return contract.__class__.from_dict(data)
