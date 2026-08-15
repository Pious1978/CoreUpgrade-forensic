# research/data/tracked_series.py
import pandas as pd
from research.data.provenance_graph import FeatureNode, TemporalDomain

class TrackedSeries:
    def __init__(self, series: pd.Series, node: FeatureNode):
        self._s = series
        self.node = node

    def shift(self, periods: int = 1):
        new_domain = self.node.domain.shift(periods)
        new_node = FeatureNode(
            name=f"{self.node.name}.shift({periods})",
            operation="shift",
            domain=new_domain,
            parents=[self.node],
            metadata={"periods": periods}
        )
        return TrackedSeries(self._s.shift(periods), new_node)

    def rolling(self, window: int, center: bool = False):
        new_domain = self.node.domain.rolling(window, center=center)
        new_node = FeatureNode(
            name=f"{self.node.name}.rolling({window})",
            operation="rolling",
            domain=new_domain,
            parents=[self.node],
            metadata={"window": window, "center": center}
        )
        
        class TrackedRolling:
            def __init__(self, rolling_obj, node):
                self._r = rolling_obj
                self.node = node
            
            def mean(self):
                # We propagate the node created by the rolling definition
                mean_node = FeatureNode(
                    name=f"{self.node.name}.mean()",
                    operation="rolling.mean",
                    domain=self.node.domain,
                    parents=[self.node],
                    metadata={}
                )
                return TrackedSeries(self._r.mean(), mean_node)

            def std(self):
                std_node = FeatureNode(
                    name=f"{self.node.name}.std()",
                    operation="rolling.std",
                    domain=self.node.domain,
                    parents=[self.node],
                    metadata={}
                )
                return TrackedSeries(self._r.std(), std_node)

        return TrackedRolling(self._s.rolling(window, center=center), new_node)

    def _binary_op(self, other, op_func, op_name, symbol):
        if isinstance(other, TrackedSeries):
            new_domain = self.node.domain.combine(other.node.domain)
            parents = [self.node, other.node]
            other_s = other._s
            other_name = other.node.name
        else:
            # Scalar or raw pandas series (no future leakage introduced by scalars)
            new_domain = self.node.domain
            parents = [self.node]
            other_s = other
            other_name = str(other)

        new_node = FeatureNode(
            name=f"({self.node.name} {symbol} {other_name})",
            operation=op_name,
            domain=new_domain,
            parents=parents,
            metadata={}
        )
        return TrackedSeries(op_func(self._s, other_s), new_node)

    # Magic methods for vectorization mapping
    def __add__(self, other): return self._binary_op(other, lambda x, y: x + y, "add", "+")
    def __sub__(self, other): return self._binary_op(other, lambda x, y: x - y, "sub", "-")
    def __mul__(self, other): return self._binary_op(other, lambda x, y: x * y, "mul", "*")
    def __truediv__(self, other): return self._binary_op(other, lambda x, y: x / y, "div", "/")
    
    def __gt__(self, other): return self._binary_op(other, lambda x, y: x > y, "gt", ">")
    def __lt__(self, other): return self._binary_op(other, lambda x, y: x < y, "lt", "<")
    def __ge__(self, other): return self._binary_op(other, lambda x, y: x >= y, "ge", ">=")
    def __le__(self, other): return self._binary_op(other, lambda x, y: x <= y, "le", "<=")
    def __eq__(self, other): return self._binary_op(other, lambda x, y: x == y, "eq", "==")
    
    def __and__(self, other): return self._binary_op(other, lambda x, y: x & y, "and", "&")
    def __or__(self, other): return self._binary_op(other, lambda x, y: x | y, "or", "|")
