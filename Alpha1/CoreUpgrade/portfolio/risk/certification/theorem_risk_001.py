# portfolio/risk/certification/theorem_risk_001.py
from portfolio.contracts.portfolio_certificate import PortfolioCertificate
from portfolio.risk.contracts.risk_snapshot import RiskSnapshot
from portfolio.contracts.universe_contract import UniverseCertificate

class RiskIntegrityTheorem:
    id = "THEOREM-RISK-001"
    
    @classmethod
    def verify(
        cls, 
        portfolio_cert: PortfolioCertificate, 
        risk_snapshot: RiskSnapshot, 
        universe_cert: UniverseCertificate
    ) -> dict:
        
        # 1. Universe Alignment
        if risk_snapshot.universe_hash != universe_cert.certificate_hash:
            return {
                "certified": False, 
                "reason": "Risk model was calculated on a different universe than the one certified for allocation."
            }
            
        # 2. Portfolio Binding
        if portfolio_cert.risk_hash != risk_snapshot.snapshot_hash:
            return {
                "certified": False,
                "reason": "Portfolio Certificate risk hash does not match the provided Risk Snapshot."
            }
            
        return {"certified": True}


# portfolio/risk/certification/theorem_risk_replay_001.py
class RiskReplayTheorem:
    id = "THEOREM-RISK-REPLAY-001"
    
    @classmethod
    def verify(
        cls, 
        original_snapshot: RiskSnapshot,
        universe: UniverseCertificate,
        price_provider: PointInTimePriceHistory,
        factor_provider: PointInTimeFactorProvider
    ) -> dict:
        
        current_env = RiskSnapshotEngine._capture_environment()
        
        # 1. Hardware/Software Drift Check
        if current_env != original_snapshot.numerical_environment:
            return {
                "certified": False,
                "reason": "Numerical Environment Drift Detected. Exact reproduction of eigenvectors/matrix inversions cannot be guaranteed.",
                "original_env": original_snapshot.numerical_environment,
                "current_env": current_env
            }
            
        # 2. Deterministic Replay
        replayed_snapshot = RiskSnapshotEngine.generate(
            universe, price_provider, factor_provider, original_snapshot.timestamp
        )
        
        if replayed_snapshot.snapshot_hash != original_snapshot.snapshot_hash:
            return {
                "certified": False,
                "reason": "Deterministic risk generation failed. Matrix math or metadata has drifted."
            }
            
        return {"certified": True}
