import numpy as np
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine for evaluating trading strategies."""

    def __init__(self, initial_balance=100000, commission=0.001):
        self.initial_balance = initial_balance
        self.commission = commission

    def backtest_predictions(self, prices, predictions):
        """
        Backtest a simple strategy: buy on BUY signal, sell on SELL signal.

        Args:
            prices: array of prices
            predictions: array of BUY/SELL/HOLD signals

        Returns:
            backtest results dict
        """
        balance = self.initial_balance
        position = 0
        entry_price = 0
        trades = []
        portfolio_values = [balance]

        for i, (price, signal) in enumerate(zip(prices, predictions)):
            if signal == "BUY" and position == 0:
                position = 1
                entry_price = price
                cost = price * (1 + self.commission)
                trades.append({
                    "type": "BUY",
                    "price": price,
                    "date": i,
                    "cost": cost
                })

            elif signal == "SELL" and position == 1:
                position = 0
                proceeds = price * (1 - self.commission)
                profit = (proceeds - entry_price) / entry_price
                trades.append({
                    "type": "SELL",
                    "price": price,
                    "date": i,
                    "profit_pct": profit * 100
                })
                balance *= (1 + profit)

            # Update portfolio value
            if position == 1:
                current_value = balance * (price / entry_price)
            else:
                current_value = balance

            portfolio_values.append(current_value)

        # Final valuation
        if position == 1:
            final_value = balance * (prices[-1] / entry_price)
        else:
            final_value = balance

        total_return = (final_value - self.initial_balance) / self.initial_balance * 100
        win_trades = sum(1 for t in trades if t.get("profit_pct", 0) > 0)
        total_trades = len([t for t in trades if t["type"] == "SELL"])

        return {
            "initial_balance": self.initial_balance,
            "final_balance": final_value,
            "total_return_pct": total_return,
            "trades": trades,
            "win_trades": win_trades,
            "total_trades": total_trades,
            "win_rate": (win_trades / total_trades * 100) if total_trades > 0 else 0,
            "portfolio_values": portfolio_values
        }

    def backtest_rl_agent(self, prices, agent):
        """
        Backtest RL agent on historical prices.

        Args:
            prices: array of historical prices
            agent: RLTradingAgent instance

        Returns:
            backtest results
        """
        from rl_trading_agent import TradingEnvironment

        env = TradingEnvironment(prices, initial_balance=self.initial_balance)
        env.reset()

        state = env.get_state()
        trades = []
        portfolio_values = [self.initial_balance]
        actions_log = []

        while env.current_step < len(prices) - 1:
            action = agent.select_action(state, training=False)
            actions_log.append(action)

            next_state, reward, done, info = env.step(action)

            if action == 1:  # Buy
                trades.append({
                    "type": "BUY",
                    "price": prices[env.current_step - 1],
                    "date": env.current_step - 1
                })

            elif action == 2:  # Sell
                trades.append({
                    "type": "SELL",
                    "price": prices[env.current_step - 1],
                    "date": env.current_step - 1,
                    "profit_pct": reward
                })

            portfolio_values.append(info.get("balance", env.balance))

            if next_state is None or done:
                break
            state = next_state

        final_balance = env.balance
        total_return = (final_balance - self.initial_balance) / self.initial_balance * 100
        win_trades = sum(1 for t in trades if t.get("profit_pct", 0) > 0)
        total_trades = len([t for t in trades if t["type"] == "SELL"])

        return {
            "initial_balance": self.initial_balance,
            "final_balance": final_balance,
            "total_return_pct": total_return,
            "trades": trades,
            "win_trades": win_trades,
            "total_trades": total_trades,
            "win_rate": (win_trades / total_trades * 100) if total_trades > 0 else 0,
            "portfolio_values": portfolio_values,
            "actions": actions_log
        }
