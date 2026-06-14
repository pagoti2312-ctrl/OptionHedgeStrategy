import numpy as np
import logging
from collections import defaultdict
from sklearn.neural_network import MLPRegressor

logger = logging.getLogger(__name__)


class TradingEnvironment:
    """Simulated trading environment for RL agent."""

    def __init__(self, prices, initial_balance=10000):
        self.prices = np.array(prices)
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0  # 0=no position, 1=long
        self.entry_price = 0
        self.current_step = 0
        self.max_steps = len(prices) - 1

    def reset(self):
        """Reset environment to initial state."""
        self.balance = self.initial_balance
        self.position = 0
        self.entry_price = 0
        self.current_step = 0

    def step(self, action):
        """
        Execute action: 0=hold, 1=buy, 2=sell
        Returns: (state, reward, done, info)
        """
        if self.current_step >= self.max_steps:
            return None, 0, True, {}

        current_price = self.prices[self.current_step]
        reward = 0
        done = self.current_step >= self.max_steps - 1

        if action == 1 and self.position == 0:  # Buy
            self.position = 1
            self.entry_price = current_price

        elif action == 2 and self.position == 1:  # Sell
            profit = current_price - self.entry_price
            reward = profit / self.entry_price * 100  # Profit as % return
            self.balance += profit
            self.position = 0

        elif action == 0:  # Hold
            if self.position == 1:
                # Unrealized P&L penalty to encourage closing positions
                unrealized = (current_price - self.entry_price) / self.entry_price
                reward = unrealized * 0.1

        self.current_step += 1
        state = self.get_state()

        return state, reward, done, {"balance": self.balance, "price": current_price}

    def get_state(self):
        """Get current state features."""
        if self.current_step >= len(self.prices):
            return np.zeros(5)

        current_price = self.prices[self.current_step]
        ma5 = np.mean(self.prices[max(0, self.current_step - 5):self.current_step + 1])
        ma20 = np.mean(self.prices[max(0, self.current_step - 20):self.current_step + 1])
        price_trend = (current_price - ma5) / ma5 if ma5 > 0 else 0
        volatility = np.std(self.prices[max(0, self.current_step - 10):self.current_step + 1])

        return np.array([
            current_price,
            ma5,
            ma20,
            price_trend,
            volatility
        ])


class RLTradingAgent:
    """Reinforcement Learning agent for trading using Q-learning with neural networks."""

    def __init__(self, learning_rate=0.01, gamma=0.95, epsilon=0.1):
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.actions = [0, 1, 2]  # 0=hold, 1=buy, 2=sell
        self.q_network = MLPRegressor(
            hidden_layer_sizes=(64, 32),
            learning_rate_init=learning_rate,
            max_iter=100,
            random_state=42,
            warm_start=True
        )
        self.is_trained = False

    def select_action(self, state, training=True):
        """Select action using epsilon-greedy strategy."""
        if training and np.random.random() < self.epsilon:
            return np.random.choice(self.actions)

        q_values = self._predict_q_values(state)
        return self.actions[np.argmax(q_values)]

    def _predict_q_values(self, state):
        """Predict Q-values for all actions."""
        if not self.is_trained:
            return np.ones(len(self.actions))

        try:
            q_values = []
            for action in self.actions:
                state_action = np.concatenate([state, [action]])
                q_val = self.q_network.predict(state_action.reshape(1, -1))[0]
                q_values.append(q_val)
            return np.array(q_values)
        except:
            return np.ones(len(self.actions))

    def train(self, prices, episodes=10):
        """Train agent on historical price data."""
        logger.info(f"Training RL agent for {episodes} episodes...")

        try:
            training_data_X = []
            training_data_y = []

            for episode in range(episodes):
                env = TradingEnvironment(prices)
                env.reset()
                state = env.get_state()
                total_reward = 0

                while True:
                    action = self.select_action(state, training=True)
                    next_state, reward, done, info = env.step(action)

                    if next_state is not None:
                        # Q-learning update
                        next_q_values = self._predict_q_values(next_state)
                        target = reward + self.gamma * np.max(next_q_values)

                        # Store training data
                        state_action = np.concatenate([state, [action]])
                        training_data_X.append(state_action)
                        training_data_y.append(target)

                        state = next_state
                        total_reward += reward

                    if done:
                        break

                if (episode + 1) % max(1, episodes // 5) == 0:
                    logger.info(f"Episode {episode + 1}/{episodes}, Balance: ₹{env.balance:.2f}, Total Reward: {total_reward:.2f}")

            if training_data_X:
                X = np.array(training_data_X)
                y = np.array(training_data_y)
                self.q_network.fit(X, y)
                self.is_trained = True
                logger.info("RL agent training complete!")
                return True

            return False

        except Exception as e:
            logger.error(f"Training error: {e}")
            return False

    def generate_signal(self, prices, lookback=50):
        """Generate trading signal based on learned policy."""
        if len(prices) < lookback:
            return None

        try:
            env = TradingEnvironment(prices[-lookback:])
            env.reset()
            state = env.get_state()

            actions_taken = []
            states_visited = []

            while env.current_step < len(prices) - lookback - 1:
                action = self.select_action(state, training=False)
                actions_taken.append(action)
                states_visited.append(state)

                next_state, _, done, _ = env.step(action)
                if next_state is None or done:
                    break
                state = next_state

            current_price = prices[-1]
            recent_actions = actions_taken[-5:] if actions_taken else []

            buy_count = recent_actions.count(1)
            sell_count = recent_actions.count(2)

            if buy_count > sell_count:
                signal = "BUY"
                confidence = (buy_count / len(recent_actions) * 100) if recent_actions else 50
            elif sell_count > buy_count:
                signal = "SELL"
                confidence = (sell_count / len(recent_actions) * 100) if recent_actions else 50
            else:
                signal = "HOLD"
                confidence = 50

            return {
                "signal": signal,
                "confidence": min(confidence, 95),
                "current_price": current_price,
                "final_balance": env.balance,
                "actions": recent_actions
            }

        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            return None
