class BrokerIntegrationError(Exception):
    """Base exception for all broker-related errors."""
    pass

class BrokerAuthenticationError(BrokerIntegrationError):
    """Raised when the broker API rejects credentials or tokens expire."""
    pass

class BrokerRateLimitError(BrokerIntegrationError):
    """Raised when the broker's API rate limits are exceeded."""
    pass

class BrokerNetworkError(BrokerIntegrationError):
    """Raised on timeouts, DNS failures, or unreachable broker endpoints."""
    pass

class BrokerOrderRejectionError(BrokerIntegrationError):
    """Raised when the broker explicitly rejects an order submission (e.g., invalid tick size)."""
    pass
