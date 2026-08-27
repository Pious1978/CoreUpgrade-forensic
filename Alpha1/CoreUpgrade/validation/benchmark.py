import numpy as np

class BenchmarkEngine:
    """Calculates benchmark relative performance metrics (Alpha, Beta, Information Ratio)."""
    
    @staticmethod
    def calculate_metrics(strategy_returns: np.ndarray, benchmark_returns: np.ndarray, risk_free_rate: float = 0.05):
        if len(strategy_returns) == 0 or len(benchmark_returns) == 0:
            return {"alpha": 0.0, "beta": 1.0, "information_ratio": 0.0}
        
        covariance = np.cov(strategy_returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 1.0
        
        strat_mean = np.mean(strategy_returns) * 252
        bench_mean = np.mean(benchmark_returns) * 252
        alpha = strat_mean - (risk_free_rate + beta * (bench_mean - risk_free_rate))
        
        active_returns = strategy_returns - benchmark_returns
        tracking_error = np.std(active_returns) * np.sqrt(252)
        information_ratio = (np.mean(active_returns) * np.sqrt(252)) / tracking_error if tracking_error > 0 else 0.0

        return {
            "alpha": round(float(alpha), 4),
            "beta": round(float(beta), 4),
            "information_ratio": round(float(information_ratio), 4)
        }
