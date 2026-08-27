"""
Standard_Engine_Types.py
-------------------------------------------------------------------------
Enterprise Type Definition Matrix for Quant Architecture Version 4.9
"""
from dataclasses import dataclass, field
import pandas as pd

@dataclass(frozen=True)
class FeatureStore:
    """The central frozen data store containing all computed indicators and performance metrics."""
    symbol: str
    date: str
    close_price: float
    metrics: dict = field(default_factory=dict)  
    raw_dfs: dict = field(default_factory=dict, repr=False)  

@dataclass(frozen=True)
class EngineResult:
    """The uniform return object enforced across all modular scanning engines."""
    engine_name: str
    version: str
    score: float
    verdict: str        
    confidence: float   
    metrics: dict        
    commentary: str
    execution_time_ms: float = 0.0  # Automatic engine performance profiling