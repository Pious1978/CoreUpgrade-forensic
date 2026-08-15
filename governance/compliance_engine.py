from typing import Dict, Any, List, Set

class ComplianceEngine:
    """
    Independent compliance gatekeeper verifying restricted lists, watchlists, 
    and regulatory trading prohibitions.
    """
    
    def __init__(self, restricted_list: Set[str] = None, insider_blacklist: Set[str] = None):
        self.restricted_list = restricted_list or {"SUSPENDED_SYM_1", "BAN_LIST_STOCK"}
        self.insider_blacklist = insider_blacklist or set()

    def check_compliance(self, proposed_symbols: List[str]) -> List[Dict[str, Any]]:
        violations = []
        for sym in proposed_symbols:
            if sym in self.restricted_list:
                violations.append({
                    "rule": "RESTRICTED_SECURITY",
                    "severity": "BLOCK",
                    "symbol": sym,
                    "message": f"Symbol {sym} is on the institutional restricted/ban list."
                })
            if sym in self.insider_blacklist:
                violations.append({
                    "rule": "INSIDER_BLACKOUT",
                    "severity": "BLOCK",
                    "symbol": sym,
                    "message": f"Symbol {sym} is subject to an active insider blackout period."
                })
        return violations
