import pandas as pd

class CorrelationEngine:
    """
    Calculates asset-to-asset correlations to prevent portfolio concentration risk.
    """
    
    def __init__(self, price_history: pd.DataFrame, threshold: float = 0.75):
        self.prices = price_history
        self.threshold = threshold

    def check_correlation_cluster(self, active_symbols: list, candidate_symbol: str) -> bool:
        if not active_symbols or candidate_symbol not in self.prices.columns:
            return True # Safe to add if no conflict
            
        sub_df = self.prices[active_symbols + [candidate_symbol]].pct_change().dropna()
        corr_matrix = sub_df.corr()
        
        for sym in active_symbols:
            if abs(corr_matrix.loc[candidate_symbol, sym]) > self.threshold:
                return False # High correlation block triggered
                
        return True
