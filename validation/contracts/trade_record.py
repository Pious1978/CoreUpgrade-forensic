from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math
import pytz
import uuid

IST = pytz.timezone("Asia/Kolkata")
TRADE_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_DNS,
    "institutional_alpha_engine"
)

@dataclass
class TradeRecord:
    ...