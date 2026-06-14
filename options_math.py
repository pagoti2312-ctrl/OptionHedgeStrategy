import numpy as np
from scipy.stats import norm

def bsm_d1_d2(S, K, T, r, sigma, q=0.0):
    """
    Calculate d1 and d2 parameters of the Black-Scholes-Merton model.
    S: Spot price of underlying
    K: Strike price of option
    T: Time to expiration (in years, e.g., days/365)
    r: Risk-free interest rate (e.g., 0.07 for 7%)
    sigma: Volatility (annualized, e.g., 0.15 for 15%)
    q: Dividend yield (e.g., 0.0 for index/non-paying stocks)
    """
    # Safeguard against zero or negative values
    S = np.maximum(S, 1e-8)
    K = np.maximum(K, 1e-8)
    T = np.maximum(T, 1e-8)
    sigma = np.maximum(sigma, 1e-8)
    
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return d1, d2

def bsm_price(S, K, T, r, sigma, option_type='C', q=0.0):
    """
    Calculate the BSM theoretical option price.
    option_type: 'C' for Call, 'P' for Put
    """
    if T <= 0:
        # Intrinsic value at expiration
        if option_type.upper() == 'C':
            return np.maximum(S - K, 0.0)
        else:
            return np.maximum(K - S, 0.0)
            
    d1, d2 = bsm_d1_d2(S, K, T, r, sigma, q)
    
    if option_type.upper() == 'C':
        price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    elif option_type.upper() == 'P':
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
    else:
        raise ValueError("option_type must be 'C' (Call) or 'P' (Put)")
        
    return price

def calculate_greeks(S, K, T, r, sigma, option_type='C', q=0.0):
    """
    Calculate analytical BSM Greeks.
    Returns a dictionary of Delta, Gamma, Vega, and Theta.
    Theta is returned as per-calendar-day decay (divided by 365).
    """
    # Safe bounds
    T = max(T, 1e-8)
    sigma = max(sigma, 1e-8)
    S = max(S, 1e-8)
    
    d1, d2 = bsm_d1_d2(S, K, T, r, sigma, q)
    
    # Probability density of d1
    pdf_d1 = norm.pdf(d1)
    
    # Gamma (same for Call and Put)
    gamma = (np.exp(-q * T) * pdf_d1) / (S * sigma * np.sqrt(T))
    
    # Vega (same for Call and Put, returned for 1% change in sigma)
    vega = S * np.exp(-q * T) * np.sqrt(T) * pdf_d1
    vega_1pct = vega * 0.01  # typically reported as change per 1% change in volatility
    
    if option_type.upper() == 'C':
        delta = np.exp(-q * T) * norm.cdf(d1)
        # Theta for Call
        theta = (-(S * np.exp(-q * T) * pdf_d1 * sigma) / (2 * np.sqrt(T))
                 - r * K * np.exp(-r * T) * norm.cdf(d2)
                 + q * S * np.exp(-q * T) * norm.cdf(d1))
    elif option_type.upper() == 'P':
        delta = -np.exp(-q * T) * norm.cdf(-d1)
        # Theta for Put
        theta = (-(S * np.exp(-q * T) * pdf_d1 * sigma) / (2 * np.sqrt(T))
                 + r * K * np.exp(-r * T) * norm.cdf(-d2)
                 - q * S * np.exp(-q * T) * norm.cdf(-d1))
    else:
        raise ValueError("option_type must be 'C' or 'P'")
        
    # Standardize Theta to 1 day (calendar day basis)
    theta_1day = theta / 365.0
    
    return {
        'Delta': delta,
        'Gamma': gamma,
        'Vega': vega_1pct,
        'Theta': theta_1day
    }

def implied_volatility(price, S, K, T, r, option_type='C', q=0.0, max_iter=100, tolerance=1e-6):
    """
    Solve for implied volatility using the Newton-Raphson method.
    """
    if T <= 0:
        return 0.0
        
    # Set initial guess (standard guess around 20% volatility)
    sigma = 0.20
    
    for i in range(max_iter):
        fitted_price = bsm_price(S, K, T, r, sigma, option_type, q)
        diff = fitted_price - price
        
        if abs(diff) < tolerance:
            return sigma
            
        greeks = calculate_greeks(S, K, T, r, sigma, option_type, q)
        # Vega is returned for 1% change, convert back to decimal derivative
        vega = greeks['Vega'] * 100.0
        
        # Avoid division by very small numbers
        if abs(vega) < 1e-4:
            break
            
        # Update sigma using Newton step
        sigma_new = sigma - diff / vega
        
        # Keep sigma within realistic limits [1%, 500%]
        sigma = np.clip(sigma_new, 0.01, 5.0)
        
    return sigma

def expected_range_statistical(spot, iv, dte, num_std_dev=1.0):
    """
    Calculate the statistical expected upper and lower bounds of the underlying price.
    spot: Current price of underlying
    iv: Implied volatility (decimal, e.g., 0.15 for 15%)
    dte: Days to expiration (calendar days)
    num_std_dev: Number of standard deviations (1.0 = 68.2%, 2.0 = 95.4%)
    """
    T = dte / 365.0
    expected_pct_move = iv * np.sqrt(T) * num_std_dev
    
    expected_high = spot * (1 + expected_pct_move)
    expected_low = spot * (1 - expected_pct_move)
    
    return expected_high, expected_low

if __name__ == "__main__":
    # Test cases
    spot = 23000.0
    strike = 23000.0
    dte = 5.0  # 5 days to expiry
    T = dte / 365.0
    r = 0.07  # 7% Indian risk-free rate
    iv = 0.15  # 15% IV
    
    print("--- Testing Options Math Module ---")
    c_price = bsm_price(spot, strike, T, r, iv, 'C')
    p_price = bsm_price(spot, strike, T, r, iv, 'P')
    print(f"ATM Call Price: {c_price:.2f}")
    print(f"ATM Put Price: {p_price:.2f}")
    
    greeks_c = calculate_greeks(spot, strike, T, r, iv, 'C')
    print("\nATM Call Greeks:")
    for k, v in greeks_c.items():
        print(f"  {k}: {v:.5f}")
        
    solved_iv = implied_volatility(c_price, spot, strike, T, r, 'C')
    print(f"\nSolved Implied Volatility: {solved_iv*100:.2f}% (Expected: {iv*100:.2f}%)")
    
    high_1sd, low_1sd = expected_range_statistical(spot, iv, dte, 1.0)
    print(f"\nUnderlying expected range (1-SD, {dte} days): {low_1sd:.2f} to {high_1sd:.2f}")
