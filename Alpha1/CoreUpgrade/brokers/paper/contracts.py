from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional, Tuple

@dataclass(frozen=True)
class FillContract:
    execution_id: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    exchange_timestamp: int
    broker_timestamp: int
    liquidity_flag: str
    venue: str
    trade_id: str

@dataclass(frozen=True)
class MarketSnapshotContract:
    symbol: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: Decimal
    timestamp: int
    snapshot_id: str
    sequence_number: int
    exchange_timestamp: int
    provider_timestamp: int
    book_version: int
    book_depth: dict = field(default_factory=dict)

@dataclass(frozen=True)
class ExecutionReportContract:
    client_order_id: str
    broker_order_id: str
    status: OrderStatus
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Decimal
    error_message: Optional[str]
    timestamp: int
    broker_name: str
    correlation_id: Optional[str] = None
    version: int = 1

@dataclass(frozen=True)
class ExecutionOutcome:
    status: OrderStatus
    fills: Tuple[FillContract, ...]
    reports: Tuple[ExecutionReportContract, ...]
    remaining_quantity: Decimal
    error_message: Optional[str]
    latency_ms: int
    market_price: Decimal
    slippage: Decimal
    fees: Decimal
    execution_timestamp: int
    execution_latency: int
    matching_algorithm: str
    session_state: str
    liquidity_snapshot: Decimal
    execution_flags: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
