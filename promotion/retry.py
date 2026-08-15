from .exceptions import RetryablePromotionError, FatalPromotionError

class RetryPolicy:
    """Classifies structured exceptions directly without string parsing."""
    @staticmethod
    def evaluate(error: Exception) -> bool:
        if isinstance(error, FatalPromotionError):
            return False
        if isinstance(error, RetryablePromotionError):
            return True
        return False
