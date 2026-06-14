from market_data import get_live_quotes, calculate_dte, is_market_open
from options_math import expected_range_statistical, bsm_price

import sys

SYMBOL = "NIFTY"
if len(sys.argv) > 1:
    SYMBOL = sys.argv[1].upper()

if not is_market_open():
    print("Market is closed — demo will still run but live option LTPs may be unavailable.")

res = get_live_quotes([SYMBOL, "VIX"])
quotes = {}
spot = None
vix = 0
if res.get("s") == "ok":
    quotes = res.get("data", {})
    spot = quotes.get(SYMBOL, {}).get("ltp")
    vix = quotes.get("VIX", {}).get("ltp", 0)

if spot is None:
    # Fallback simulated data when NSE is closed or live quotes unavailable
    print("Live quotes unavailable — using simulated demo values.")
    if SYMBOL == "NIFTY":
        spot = 24750.00
        vix = 14.5
    elif SYMBOL == "SENSEX":
        spot = 83300.00
        vix = 13.8
    else:
        spot = 1000.0
        vix = 20.0

iv = vix / 100.0
r = 0.07

dte = calculate_dte(SYMBOL)
T = dte / 365.0

high_spot, low_spot = expected_range_statistical(spot, iv, dte, num_std_dev=1.0)

strike_step = 50 if SYMBOL in ["FINNIFTY", "MIDCPNIFTY"] else 100
atm_strike = round(spot / strike_step) * strike_step

ce_current = bsm_price(spot, atm_strike, T, r, iv, option_type='C')
pe_current = bsm_price(spot, atm_strike, T, r, iv, option_type='P')
ce_min = bsm_price(high_spot, atm_strike, T, r, iv, option_type='C')
ce_max = bsm_price(low_spot, atm_strike, T, r, iv, option_type='C')
pe_min = bsm_price(low_spot, atm_strike, T, r, iv, option_type='P')
pe_max = bsm_price(high_spot, atm_strike, T, r, iv, option_type='P')

print(f"Symbol: {SYMBOL}")
print(f"Spot: {spot:.2f}")
print(f"VIX: {vix:.2f}%")
print(f"DTE: {dte:.1f} days")
print(f"ATM Strike: {atm_strike}")
print(f"Expected Underlying Low: {low_spot:.2f}")
print(f"Expected Underlying High: {high_spot:.2f}")
print(f"ATM CE Current (BSM): ₹{ce_current:.2f}")
print(f"  Expected CE Min: ₹{max(ce_min,0.01):.2f}")
print(f"  Expected CE Max: ₹{ce_max:.2f}")
print(f"ATM PE Current (BSM): ₹{pe_current:.2f}")
print(f"  Expected PE Min: ₹{max(pe_min,0.01):.2f}")
print(f"  Expected PE Max: ₹{pe_max:.2f}")
