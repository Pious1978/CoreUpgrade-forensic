from enum import Enum

class BrokerId(Enum):
    PAPER = "PAPER"
    IBKR = "IBKR"
    ZERODHA = "ZERODHA"
    ALPACA = "ALPACA"

class Environment(Enum):
    DEVELOPMENT = "DEVELOPMENT"
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"
    REPLAY = "REPLAY"

class ExecutionMode(Enum):
    SIMULATED = "SIMULATED"
    PAPER = "PAPER"
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"
