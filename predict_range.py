import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from options_math import bsm_price, expected_range_statistical, calculate_greeks

def predict_option_range_statistical(spot, strike, dte, iv, r, option_type='C', num_std_dev=1.0):
    """
    Predict option High and Low prices using statistical ranges of the underlying.
    1. Calculate statistical range of underlying (expected High and Low).
    2. Price the option at those extreme points at the end of the DTE window (or standard pricing).
    """
    # 1. Get underlying statistical range
    expected_high, expected_low = expected_range_statistical(spot, iv, dte, num_std_dev)
    
    # 2. Get option prices at the expected high/low spot prices
    # Note: As time passes, DTE will decrease. Let's assume we are looking at the price
    # at the expected high/low target, holding DTE constant or decaying it.
    # Let's price it assuming the move happens intraday (holding DTE constant)
    T = dte / 365.0
    
    current_price = bsm_price(spot, strike, T, r, iv, option_type)
    price_at_high = bsm_price(expected_high, strike, T, r, iv, option_type)
    price_at_low = bsm_price(expected_low, strike, T, r, iv, option_type)
    
    # Depending on option type (Call or Put), high spot price maps to high/low option price
    if option_type.upper() == 'C':
        predicted_high = price_at_high
        predicted_low = price_at_low
    else:
        predicted_high = price_at_low
        predicted_low = price_at_high
        
    return {
        'current_price': current_price,
        'underlying_expected_range': (expected_low, expected_high),
        'option_predicted_low': min(predicted_low, current_price), # Option can decay further or move against us
        'option_predicted_high': max(predicted_high, current_price)
    }

def generate_synthetic_data(num_samples=2000):
    """
    Generate synthetic options data for training the machine learning models.
    Simulates ATM, near OTM, and near ITM options for Indian Index trading.
    """
    np.random.seed(42)
    
    # Spot centered around 23000
    spot = np.random.normal(23000, 200, num_samples)
    
    # Select strike relative to spot to capture ATM, OTM, ITM
    # In Indian markets, strikes are usually at 50/100 intervals.
    strike_diff = np.random.choice([-200, -100, 0, 100, 200], num_samples)
    strike = np.round(spot / 100) * 100 + strike_diff
    
    # DTE between 0.1 (expiry day afternoon) and 7.0 (weekly cycle start)
    dte = np.random.uniform(0.1, 7.0, num_samples)
    T = dte / 365.0
    
    # Volatility and macroeconomic factors
    india_vix = np.random.uniform(11, 20, num_samples) / 100.0  # Decimal
    iv_skew = np.random.normal(0.02, 0.01, num_samples)          # IV skew premium
    iv = india_vix + iv_skew
    
    r = 0.07 # Indian risk-free rate is relatively stable around 6.5% - 7%
    option_type = np.random.choice(['C', 'P'], num_samples)
    
    # Put-Call Ratio (PCR) between 0.6 and 1.4
    pcr = np.random.uniform(0.6, 1.4, num_samples)
    
    # Calculate base BSM prices
    prices = []
    deltas = []
    gammas = []
    thetas = []
    
    for i in range(num_samples):
        p = bsm_price(spot[i], strike[i], T[i], r, iv[i], option_type[i])
        g = calculate_greeks(spot[i], strike[i], T[i], r, iv[i], option_type[i])
        prices.append(p)
        deltas.append(g['Delta'])
        gammas.append(g['Gamma'])
        thetas.append(g['Theta'])
        
    prices = np.array(prices)
    
    # Simulate high and low prices of options by adding random intraday swings scaled by Vega & Gamma
    intraday_underlying_pct_move = np.random.exponential(0.008, num_samples) # Average ~0.8% swing
    
    # High prices: option moves in our favor + volatility expansion
    option_high_noise = np.random.uniform(1.05, 1.25, num_samples)
    option_high = prices * option_high_noise + (np.abs(deltas) * spot * intraday_underlying_pct_move)
    
    # Low prices: option moves against us + volatility contraction + theta decay
    option_low_noise = np.random.uniform(0.70, 0.95, num_samples)
    option_low = np.maximum(prices * option_low_noise - (np.abs(deltas) * spot * intraday_underlying_pct_move) + thetas, 0.05) # Floor at 0.05 paisa
    
    # Compile into DataFrame
    df = pd.DataFrame({
        'spot': spot,
        'strike': strike,
        'dte': dte,
        'iv': iv,
        'india_vix': india_vix,
        'pcr': pcr,
        'is_call': (option_type == 'C').astype(int),
        'delta': deltas,
        'gamma': gammas,
        'theta': thetas,
        'current_price': prices,
        'option_low': option_low,
        'option_high': option_high
    })
    
    return df

class OptionRangeMLModel:
    """
    Quantile Regression Pipeline to predict High/Low bounds.
    Uses LightGBM Quantile Regressors.
    """
    def __init__(self):
        # We define two models: one for the 10th percentile (Low) and one for the 90th percentile (High)
        self.model_low = lgb.LGBMRegressor(
            objective='quantile',
            alpha=0.10,
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=31,
            random_state=42,
            verbose=-1
        )
        
        self.model_high = lgb.LGBMRegressor(
            objective='quantile',
            alpha=0.90,
            n_estimators=100,
            learning_rate=0.05,
            num_leaves=31,
            random_state=42,
            verbose=-1
        )
        
        self.features = ['spot', 'strike', 'dte', 'iv', 'india_vix', 'pcr', 'is_call', 'delta', 'gamma', 'theta', 'current_price']
        
    def train(self, df):
        X = df[self.features]
        y_low = df['option_low']
        y_high = df['option_high']
        
        # Train Low model
        self.model_low.fit(X, y_low)
        # Train High model
        self.model_high.fit(X, y_high)
        
    def predict(self, input_features_df):
        """
        Input features should match self.features
        """
        X = input_features_df[self.features]
        pred_low = self.model_low.predict(X)
        pred_high = self.model_high.predict(X)
        
        # Ensure predicted low is bounded by 0.05 minimum and high is greater than low
        pred_low = np.maximum(pred_low, 0.05)
        pred_high = np.maximum(pred_high, pred_low + 0.05)
        
        return pred_low, pred_high

if __name__ == "__main__":
    print("--- 1. Testing Statistical Range Method ---")
    spot = 23000.0
    r = 0.07
    iv = 0.15
    dte = 5.0
    
    # ATM Call (Strike 23000)
    atm_call_stats = predict_option_range_statistical(spot, 23000.0, dte, iv, r, 'C')
    print("ATM Call (Strike 23000):")
    print(f"  Current Price: {atm_call_stats['current_price']:.2f}")
    print(f"  Underlying expected range: {atm_call_stats['underlying_expected_range'][0]:.2f} - {atm_call_stats['underlying_expected_range'][1]:.2f}")
    print(f"  Option predicted Low/High: {atm_call_stats['option_predicted_low']:.2f} - {atm_call_stats['option_predicted_high']:.2f}")
    
    # Near OTM Call (Strike 23200)
    otm_call_stats = predict_option_range_statistical(spot, 23200.0, dte, iv, r, 'C')
    print("\nNear OTM Call (Strike 23200):")
    print(f"  Current Price: {otm_call_stats['current_price']:.2f}")
    print(f"  Option predicted Low/High: {otm_call_stats['option_predicted_low']:.2f} - {otm_call_stats['option_predicted_high']:.2f}")

    # Near ITM Call (Strike 22800)
    itm_call_stats = predict_option_range_statistical(spot, 22800.0, dte, iv, r, 'C')
    print("\nNear ITM Call (Strike 22800):")
    print(f"  Current Price: {itm_call_stats['current_price']:.2f}")
    print(f"  Option predicted Low/High: {itm_call_stats['option_predicted_low']:.2f} - {itm_call_stats['option_predicted_high']:.2f}")

    print("\n--- 2. Testing ML Quantile Regression Method ---")
    print("Generating synthetic options dataset...")
    df = generate_synthetic_data(2500)
    
    # Split into train & test
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
    print(f"Training dataset size: {train_df.shape[0]}")
    print(f"Testing dataset size: {test_df.shape[0]}")
    
    # Initialize and train ML pipeline
    range_predictor = OptionRangeMLModel()
    range_predictor.train(train_df)
    print("Quantile Regression models trained successfully!")
    
    # Evaluate on a sample of test data
    sample_test = test_df.sample(5, random_state=100)
    pred_lows, pred_highs = range_predictor.predict(sample_test)
    
    print("\nPredictions vs Actual High/Low on Test Sample:")
    for i in range(len(sample_test)):
        row = sample_test.iloc[i]
        opt_type = 'Call' if row['is_call'] == 1 else 'Put'
        print(f"\nSample {i+1}: {opt_type} Strike {row['strike']:.0f} (Spot: {row['spot']:.0f}, DTE: {row['dte']:.2f} days)")
        print(f"  Current Market Price: {row['current_price']:.2f}")
        print(f"  Actual High / Low:    {row['option_high']:.2f} / {row['option_low']:.2f}")
        print(f"  Predicted High / Low: {pred_highs[i]:.2f} / {pred_lows[i]:.2f}")
