import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)


class StockPricePredictor:
    def __init__(self, window_size=20, test_size=0.2):
        self.window_size = window_size
        self.test_size = test_size
        self.model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.scaler = StandardScaler()
        self.is_trained = False

    def create_features(self, data):
        """Create lagged features from price data."""
        if len(data) < self.window_size:
            return None, None

        X, y = [], []
        for i in range(len(data) - self.window_size):
            X.append(data[i:i + self.window_size])
            y.append(data[i + self.window_size])

        return np.array(X), np.array(y)

    def train(self, historical_prices):
        """Train model on historical price data."""
        try:
            if len(historical_prices) < self.window_size + 5:
                logger.warning("Insufficient data for training")
                return False

            X, y = self.create_features(historical_prices)
            if X is None:
                return False

            X_flat = X.reshape(X.shape[0], -1)
            X_scaled = self.scaler.fit_transform(X_flat)

            self.model.fit(X_scaled, y)
            self.is_trained = True
            logger.info("Model trained successfully")
            return True
        except Exception as e:
            logger.error(f"Training error: {e}")
            return False

    def predict_next(self, historical_prices, steps=5):
        """Predict next N prices."""
        if not self.is_trained or len(historical_prices) < self.window_size:
            return None

        try:
            predictions = []
            current_data = historical_prices[-self.window_size:].copy()

            for _ in range(steps):
                X_input = current_data.reshape(1, -1)
                X_scaled = self.scaler.transform(X_input)
                pred = self.model.predict(X_scaled)[0]
                predictions.append(pred)
                current_data = np.append(current_data[1:], pred)

            return {
                "predictions": predictions,
                "current_price": historical_prices[-1],
                "trend": "UP" if predictions[-1] > historical_prices[-1] else "DOWN",
                "confidence": float(self.model.score(self.scaler.transform(
                    historical_prices[-self.window_size:].reshape(1, -1)
                ), [historical_prices[-1]]) * 100)
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None

    def predict_range(self, historical_prices):
        """Predict price range (support/resistance)."""
        if len(historical_prices) < 5:
            return None

        pred = self.predict_next(historical_prices, steps=5)
        if pred is None:
            return None

        preds = pred["predictions"]
        current = pred["current_price"]

        return {
            "current": current,
            "predicted_high": max(preds),
            "predicted_low": min(preds),
            "trend": pred["trend"],
            "confidence": pred["confidence"]
        }
