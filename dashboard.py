from flask import Flask, render_template, jsonify, request
import numpy as np
import json
import logging
from price_predictor import StockPricePredictor
from rl_trading_agent import RLTradingAgent
from backtest_engine import BacktestEngine

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Index symbols
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX"]


@app.route('/')
def index():
    """Dashboard home page."""
    return render_template('index.html', symbols=INDEX_SYMBOLS)


@app.route('/api/predict/<symbol>')
def api_predict(symbol):
    """Get ML price prediction for a symbol."""
    if symbol not in INDEX_SYMBOLS:
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        # Generate synthetic historical data
        np.random.seed(42)
        base_prices = {
            "NIFTY": 18000,
            "BANKNIFTY": 45000,
            "FINNIFTY": 20000,
            "MIDCPNIFTY": 20000,
            "SENSEX": 60000
        }

        base_price = base_prices.get(symbol, 18000)
        historical_prices = []
        current_price = base_price

        for _ in range(100):
            change = np.random.normal(0, base_price * 0.003)
            current_price = max(current_price + change, base_price * 0.8)
            historical_prices.append(current_price)

        historical_prices = np.array(historical_prices)

        predictor = StockPricePredictor(window_size=20)
        if not predictor.train(historical_prices):
            return jsonify({"error": "Training failed"}), 500

        pred = predictor.predict_range(historical_prices)

        return jsonify({
            "symbol": symbol,
            "current": pred["current"],
            "predicted_high": pred["predicted_high"],
            "predicted_low": pred["predicted_low"],
            "trend": pred["trend"],
            "confidence": pred["confidence"]
        })

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/trade_signal/<symbol>')
def api_trade_signal(symbol):
    """Get RL trading signal for a symbol."""
    if symbol not in INDEX_SYMBOLS:
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        np.random.seed(42)
        base_prices = {
            "NIFTY": 18000,
            "BANKNIFTY": 45000,
            "FINNIFTY": 20000,
            "MIDCPNIFTY": 20000,
            "SENSEX": 60000
        }

        base_price = base_prices.get(symbol, 18000)
        historical_prices = []
        current_price = base_price

        for _ in range(100):
            change = np.random.normal(0, base_price * 0.003)
            current_price = max(current_price + change, base_price * 0.8)
            historical_prices.append(current_price)

        historical_prices = np.array(historical_prices)

        agent = RLTradingAgent()
        if not agent.train(historical_prices, episodes=5):
            return jsonify({"error": "Training failed"}), 500

        signal_data = agent.generate_signal(historical_prices)

        return jsonify({
            "symbol": symbol,
            "signal": signal_data["signal"],
            "confidence": signal_data["confidence"],
            "current_price": signal_data["current_price"],
            "final_balance": signal_data["final_balance"]
        })

    except Exception as e:
        logger.error(f"Trade signal error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/backtest/<symbol>')
def api_backtest(symbol):
    """Run backtest on ML predictions."""
    if symbol not in INDEX_SYMBOLS:
        return jsonify({"error": "Invalid symbol"}), 400

    try:
        np.random.seed(42)
        base_prices = {
            "NIFTY": 18000,
            "BANKNIFTY": 45000,
            "FINNIFTY": 20000,
            "MIDCPNIFTY": 20000,
            "SENSEX": 60000
        }

        base_price = base_prices.get(symbol, 18000)
        historical_prices = []
        current_price = base_price

        for _ in range(100):
            change = np.random.normal(0, base_price * 0.003)
            current_price = max(current_price + change, base_price * 0.8)
            historical_prices.append(current_price)

        historical_prices = np.array(historical_prices)

        # Generate predictions
        predictor = StockPricePredictor(window_size=20)
        predictor.train(historical_prices)

        predictions = []
        for i, price in enumerate(historical_prices):
            pred = predictor.predict_range(historical_prices[:i+1])
            if pred["trend"] == "UP":
                predictions.append("BUY")
            else:
                predictions.append("SELL")

        # Run backtest
        engine = BacktestEngine(initial_balance=100000)
        results = engine.backtest_predictions(historical_prices, predictions)

        return jsonify({
            "symbol": symbol,
            "initial_balance": results["initial_balance"],
            "final_balance": round(results["final_balance"], 2),
            "total_return_pct": round(results["total_return_pct"], 2),
            "win_rate": round(results["win_rate"], 2),
            "total_trades": results["total_trades"],
            "win_trades": results["win_trades"],
            "trades": results["trades"][:10]  # Last 10 trades
        })

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
