"""
Fyers-based market data provider (legacy, kept for reference).
⚠️ Requires daily token refresh - consider switching to NSE provider
"""
import os
import json
import datetime
import urllib.request
import urllib.parse
import logging
from market_data_provider import MarketDataProvider
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

TOKEN_FILE = "fyers_token.txt"
DATA_URL = "https://api-t1.fyers.in/data-rest/v3/quotes"


class FyersDataProvider(MarketDataProvider):
    """Fyers API data provider - ⚠️ requires daily token refresh"""
    
    def __init__(self):
        self.token_file = TOKEN_FILE
        self.data_url = DATA_URL
        
        # NSE expiry weekday mapping
        self.expiry_weekdays = {
            "FINNIFTY": 1,
            "BANKNIFTY": 2,
            "NIFTY": 3,
            "MIDCPNIFTY": 0
        }
        
        # Fyers symbol mapping
        self.index_mapping = {
            "NIFTY": "NSE:NIFTY50-INDEX",
            "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
            "FINNIFTY": "NSE:FINNIFTY-INDEX",
            "MIDCPNIFTY": "NSE:MIDCPNIFTY-INDEX",
            "VIX": "NSE:INDIAVIX-INDEX"
        }

    def get_auth_token(self) -> str:
        """Read the access token saved by fyers_auth.py"""
        if not os.path.exists(self.token_file):
            raise FileNotFoundError(
                f"Fyers authentication token not found at {self.token_file}. "
                "Please run 'python fyers_auth.py' first to authenticate."
            )
        with open(self.token_file, "r") as f:
            return f.read().strip()

    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        """
        Fetch live market quotes for a list of symbols.
        symbols_list: List of friendly names (e.g. ['NIFTY', 'BANKNIFTY'])
        """
        try:
            token = self.get_auth_token()
        except FileNotFoundError as e:
            return {"s": "error", "message": str(e)}

        # Convert friendly names to Fyers symbols
        fyers_symbols = [self.index_mapping.get(s, s) for s in symbols_list]
        symbols_str = ",".join(fyers_symbols)
        params = {"symbols": symbols_str}
        query_string = urllib.parse.urlencode(params)
        url = f"{self.data_url}?{query_string}"
        
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
                    quotes = {}
                    data_list = res_json.get("d", [])
                    for item in data_list:
                        symbol_name = item.get("n")
                        values = item.get("v", {})
                        quotes[symbol_name] = {
                            "ltp": values.get("lp"),
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
            try:
                err_body = e.read().decode('utf-8')
                err_json = json.loads(err_body)
                return {"s": "error", "message": f"HTTP {e.code}: {err_json.get('message', e.reason)}"}
            except:
                return {"s": "error", "message": f"HTTP Error {e.code}: {e.reason}"}
        except Exception as e:
            return {"s": "error", "message": str(e)}

    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        """Fyers API doesn't provide easy option chain access - use NSE provider instead"""
        return {
            "s": "error",
            "message": "Use NSEDataProvider for option chain data instead"
        }

    def calculate_dte(self, symbol: str = "NIFTY") -> int:
        """
        Calculate calendar days remaining to the next standard weekly expiry.
        """
        if symbol not in self.expiry_weekdays:
            symbol = "NIFTY"
        
        target_weekday = self.expiry_weekdays[symbol]
        today = datetime.datetime.now().date()
        days_ahead = target_weekday - today.weekday()
        
        if days_ahead <= 0:
            days_ahead += 7
        
        return days_ahead

    def get_next_expiry(self, symbol: str = "NIFTY") -> str:
        """
        Get next standard weekly expiry in DDMMMYYYY format.
        """
        dte = self.calculate_dte(symbol)
        expiry_date = datetime.datetime.now().date() + datetime.timedelta(days=dte)
        return expiry_date.strftime("%d%b%Y").upper()
