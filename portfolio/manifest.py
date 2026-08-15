DOMAIN_NAME = "portfolio"

VERSION = "1.0"

PUBLIC_API = {
    "PortfolioAllocator": "allocator.PortfolioAllocator",
    "PortfolioOptimizer": "optimizer.PortfolioOptimizer",
    "PositionSizer": "position_sizing.PositionSizer"
}

FORBIDDEN_IMPORTS = [
    "execution"
]
