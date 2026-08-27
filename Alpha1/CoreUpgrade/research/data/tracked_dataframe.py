# research/data/tracked_dataframe.py
import pandas as pd
from research.data.provenance_graph import FeatureNode, TemporalDomain
from research.data.tracked_series import TrackedSeries

class TrackedDataFrame:
    def __init__(self, df: pd.DataFrame):
        self._df = df.copy()
        self._tracked_columns = {}
        
        # Initialize base nodes for all raw columns
        for col in df.columns:
            node = FeatureNode(
                name=f"raw('{col}')",
                operation="raw_data",
                domain=TemporalDomain(0, 0), # Base interval is strictly causal
                parents=[],
                metadata={"column": col}
            )
            self._tracked_columns[col] = TrackedSeries(self._df[col], node)

    def __getitem__(self, key: str) -> TrackedSeries:
        if key in self._tracked_columns:
            return self._tracked_columns[key]
        raise KeyError(f"Column '{key}' not found in TrackedDataFrame.")

    def __setitem__(self, key: str, value: TrackedSeries):
        if not isinstance(value, TrackedSeries):
            raise TypeError("Only TrackedSeries can be assigned to TrackedDataFrame to maintain provenance.")
        self._df[key] = value._s
        self._tracked_columns[key] = value
        
    def copy(self):
        # Shallow copy for tracking dict to mimic pandas API behavior
        new_tdf = TrackedDataFrame(self._df)
        new_tdf._tracked_columns = dict(self._tracked_columns)
        return new_tdf
