import os
import json
import datetime
import urllib.request
import urllib.parse

TOKEN_FILE = "fyers_token.txt"

# Default Fyers API V3 Production data URL
DATA_URL = "https://api-t1.fyers.in/data-rest/v3/quotes"

def get_auth_token():
    """Read the access token saved by fyers_auth.py"""
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            f"Fyers authentication token not found at {TOKEN_FILE}. "
            "Please run 'python fyers_auth.py' first to authenticate."
        )
    with open(TOKEN_FILE, "r") as f:
        return f.read().strip()

def get_live_quotes(symbols_list):
    """
    Fetch live market quotes for a list of symbols.
    symbols_list: List of Fyers symbols (e.g. ['NSE:NIFTY50-INDEX', 'NSE:INDIAVIX-INDEX'])
    """
    try:
        token = get_auth_token()
    except FileNotFoundError as e:
        return {"s": "error", "message": str(e)}

    # Format symbols as comma-separated string
    symbols_str = ",".join(symbols_list)
    params = {"symbols": symbols_str}
    query_string = urllib.parse.urlencode(params)
    url = f"{DATA_URL}?{query_string}"
    
    headers = {
        "Authorization": token,
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    req = urllib.request.Request(url, headers=headers, method="GET")
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode('utf-8')
            res_json = json.loads(res_body)
            
            if res_json.get("s") == "ok" or res_json.get("code") == 200:
                # Compile quotes into a clean dict
                quotes = {}
                # Fyers returns quote data under 'd' list
                data_list = res_json.get("d", [])
                for item in data_list:
                    symbol_name = item.get("n")
                    values = item.get("v", {})
                    quotes[symbol_name] = {
                        "ltp": values.get("lp"),          # Last price
                        "open": values.get("open_price"),
                        "high": values.get("high_price"),
                        "low": values.get("low_price"),
                        "close": values.get("prev_close_price"),
                        "change": values.get("ch"),
                        "change_pct": values.get("chp")
                    }
                return {"s": "ok", "data": quotes}
            else:
                return {
                    "s": "error", 
                    "message": res_json.get("message", "Failed to fetch quotes"),
                    "details": res_json
                }
                
    except urllib.error.HTTPError as e:
        # Read error body if available
        try:
            err_body = e.read().decode('utf-8')
            err_json = json.loads(err_body)
            return {"s": "error", "message": f"HTTP {e.code}: {err_json.get('message', e.reason)}"}
        except:
            return {"s": "error", "message": f"HTTP Error {e.code}: {e.reason}"}
    except Exception as e:
        return {"s": "error", "message": str(e)}

def calculate_dte(index_name="NIFTY"):
    """
    Calculate calendar days remaining to the next standard weekly expiry.
    - FINNIFTY: Tuesday (1)
    - BANKNIFTY: Wednesday (2)
    - NIFTY: Thursday (3)
    """
    expiry_weekdays = {
        "FINNIFTY": 1,
        "BANKNIFTY": 2,
        "NIFTY": 3,
        "MIDCPNIFTY": 0 # Monday
    }
    
    idx_upper = index_name.upper()
    target_weekday = expiry_weekdays.get(idx_upper, 3) # Default to Thursday (Nifty)
    
    now = datetime.datetime.now()
    today_date = now.date()
    today_weekday = today_date.weekday()
    
    # Calculate days until next expiry weekday
    days_ahead = target_weekday - today_weekday
    if days_ahead < 0:
        days_ahead += 7
        
    # Standard Indian Market closing time is 3:30 PM (15:30)
    market_close = datetime.datetime.combine(today_date, datetime.time(15, 30))
    
    # If today is the expiry day and the market is closed, roll over to the next week's expiry
    if days_ahead == 0 and now >= market_close:
        days_ahead = 7
        
    # Calculate fractional days remaining
    # E.g. if there are 2 days remaining, but we are in the middle of a trading day, 
    # the time decay model might benefit from fractional days.
    # For simplicity, we return calendar days (minimum of 0.1 day to prevent division by zero in pricing)
    return max(float(days_ahead), 0.1)

if __name__ == "__main__":
    print("--- Testing Fyers Live Data Client ---")
    
    # Test DTE calculations
    for idx in ["MIDCPNIFTY", "FINNIFTY", "BANKNIFTY", "NIFTY"]:
        print(f"Days to next {idx} expiry: {calculate_dte(idx):.1f} days")
        
    # Try fetching a quote (will require active fyers_token.txt to succeed)
    print("\nAttempting to query index spot prices from Fyers API...")
    symbols = ["NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX", "NSE:INDIAVIX-INDEX"]
    res = get_live_quotes(symbols)
    
    if res["s"] == "ok":
        print("\nSUCCESS! Live market quotes fetched:")
        for sym, q in res["data"].items():
            print(f"  {sym}: LTP = {q['ltp']} (Change: {q['change_pct']}%)")
    else:
        print(f"\nCould not fetch live quotes. (Expected if not logged in yet)")
        print(f"Error Message: {res['message']}")
