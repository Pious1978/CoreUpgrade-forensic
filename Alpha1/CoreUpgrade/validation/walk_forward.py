class WalkForwardEngine:
    """Splits historical data series into rolling train and validation folds to prevent overfitting."""

    @staticmethod
    def generate_folds(historical_data: list, train_size: int = 2, val_size: int = 1):
        folds = []
        n = len(historical_data)
        window = train_size + val_size
        
        for i in range(0, n - window + 1):
            train_set = historical_data[i:i+train_size]
            val_set = historical_data[i+train_size:i+window]
            folds.append({
                "train": train_set,
                "validation": val_set,
                "fold_id": f"FOLD-{i+1}"
            })
        return folds
