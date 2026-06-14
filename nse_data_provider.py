"""
NSEPython-based market data provider for live NSE data.
✨ No API key needed, no daily token refresh, truly LIVE data from NSE official source
"""
from market_data_provider import MarketDataProvider
from typing import Dict, List, Any
import datetime
import logging

logger = logging.getLogger(__name__)

try:
    import nsepython
except ImportError:
    logger.error("nsepython not installed. Run: pip install nsepython")
    nsepython = None


class NSEDataProvider(MarketDataProvider):
    """Live NSE data provider using nsepython - no authentication needed!"""
    
    def __init__(self):
        if nsepython is None:
            raise ImportError("nsepython is required. Install with: pip install nsepython")
        
        # NSE expiry weekday mapping
        self.expiry_weekdays = {
            "FINNIFTY": 1,      # Tuesday
            "BANKNIFTY": 2,     # Wednesday
            "NIFTY": 3,         # Thursday
            "MIDCPNIFTY": 0,    # Monday
            "SENSEX": 3         # Treat SENSEX like NIFTY for weekly expiry
        }
        
        # Symbol mapping to NSE format for indices
        self.index_symbols = {
            "NIFTY": "NIFTY 50",
            "BANKNIFTY": "NIFTY BANK",
            "FINNIFTY": "NIFTY FIN SERVICE",
            "MIDCPNIFTY": "NIFTY MID SELECT 50",
            "VIX": "INDIA VIX",
            "SENSEX": "SENSEX"
        }

    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        """
        Fetch live quotes from NSE (true live, no delays).

        symbols_list format: ["NIFTY", "BANKNIFTY", "VIX"] or direct NSE symbols
        """
        try:
            quotes = {}

            for symbol in symbols_list:
                try:
                    # Map friendly names to NSE symbols if needed
                    nse_symbol = self.index_symbols.get(symbol, symbol)

                    # Get live quote from NSE
                    quote_data = nsepython.nse_quote(nse_symbol)

                    if quote_data and isinstance(quote_data, dict):
                        # Handle different response formats from nsepython
                        data = quote_data.get("data") or quote_data

                        if isinstance(data, dict) and ("lastPrice" in data or "ltp" in data or "close" in data):
                            ltp = float(data.get("lastPrice") or data.get("ltp") or data.get("close") or 0)
                            quotes[symbol] = {
                                "ltp": ltp,
                                "open": float(data.get("openPrice") or data.get("open") or 0),
                                "high": float(data.get("highPrice") or data.get("high") or 0),
                                "low": float(data.get("lowPrice") or data.get("low") or 0),
                                "close": float(data.get("previousClose") or data.get("close") or 0),
                                "change": float(data.get("change") or 0),
                                "change_pct": float(data.get("pChange") or data.get("changepercent") or 0)
                            }
                        else:
                            logger.warning(f"No valid price data for symbol: {symbol}, got: {data}")
                    else:
                        logger.warning(f"Invalid response for symbol: {symbol}: {quote_data}")

                except Exception as e:
                    logger.error(f"Error fetching quote for {symbol}: {str(e)}")

            if not quotes:
                return {
                    "s": "error",
                    "message": "Failed to fetch any quotes from NSE"
                }

            return {
                "s": "ok",
                "data": quotes
            }

        except Exception as e:
            logger.error(f"NSE quote fetch error: {str(e)}")
            return {
                "s": "error",
                "message": str(e)
            }

    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        """
        Fetch option chain for a symbol.
        
        symbol: "NIFTY", "BANKNIFTY", etc.
        expiry: Optional expiry date in "DDMMMYYYY" format
        """
        try:
            if not expiry:
                expiry = self.get_next_expiry(symbol)
            
            # Get option chain from NSE
            nse_symbol = self.index_symbols.get(symbol, symbol)
            # nsepython exposes `option_chain()` which returns the option chain
            # for a given index symbol and expiry
            option_chain = None
            if hasattr(nsepython, 'option_chain'):
                # option_chain(symbol) returns a dict containing records and
                # option data for many expiries; filter by expiry if provided
                full_chain = nsepython.option_chain(nse_symbol)
                # full_chain may contain 'records' -> 'expiryDates' and 'data'
                if expiry and isinstance(full_chain, dict):
                    records = full_chain.get('records') or {}
                    exp_list = records.get('expiryDates') or records.get('expiry_dates') or []
                    # expiry provided in DDMMMYYYY; find matching
                    if expiry in exp_list:
                        # filter rows for this expiry
                        data_rows = records.get('data') or []
                        option_chain = {'records': {'data': data_rows, 'underlyingValue': records.get('underlyingValue')}, 'expiry': expiry}
                    else:
                        # return full chain if expiry not found
                        option_chain = full_chain
                else:
                    option_chain = full_chain
            elif hasattr(nsepython, 'nse_optionchain'):
                option_chain = nsepython.nse_optionchain(nse_symbol, expiry)
            else:
                raise AttributeError('nsepython does not expose option_chain()')
            
            if option_chain:
                return {
                    "s": "ok",
                    "data": option_chain,
                    "expiry": expiry
                }
            else:
                return {
                    "s": "error",
                    "message": f"No option chain data for {symbol} on {expiry}"
                }
                
        except Exception as e:
            logger.error(f"Option chain fetch error: {str(e)}")
            return {
                "s": "error",
                "message": str(e)
            }

    def calculate_dte(self, symbol: str = "NIFTY") -> int:
        """
        Calculate days to expiry for next standard weekly expiry.
        
        Expiry schedule:
        - FINNIFTY: Tuesday (weekday 1)
        - BANKNIFTY: Wednesday (weekday 2)
        - NIFTY: Thursday (weekday 3)
        - MIDCPNIFTY: Monday (weekday 0)
        """
        if symbol not in self.expiry_weekdays:
            symbol = "NIFTY"
        
        target_weekday = self.expiry_weekdays[symbol]
        today = datetime.datetime.now().date()
        days_ahead = target_weekday - today.weekday()
        
        # If target day already happened this week, next week's date
        if days_ahead <= 0:
            days_ahead += 7
        
        return days_ahead

    def get_next_expiry(self, symbol: str = "NIFTY") -> str:
        """
        Get next standard weekly expiry in DDMMMYYYY format.
        Example: "14JUN2024"
        """
        dte = self.calculate_dte(symbol)
        expiry_date = datetime.datetime.now().date() + datetime.timedelta(days=dte)
        
        # Format as DDMMMYYYY
        return expiry_date.strftime("%d%b%Y").upper()

    def is_market_open(self) -> bool:
        """
        Check if NSE market is currently open.
        NSE trading hours: 9:15 AM - 3:30 PM IST on weekdays
        """
        try:
            now = datetime.datetime.now()
            weekday = now.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
            
            # Market closed on weekends
            if weekday >= 5:
                return False
            
            # Market hours: 9:15 AM - 3:30 PM
            market_open = now.replace(hour=9, minute=15, second=0)
            market_close = now.replace(hour=15, minute=30, second=0)
            
            return market_open <= now <= market_close
            
        except Exception as e:
            logger.warning(f"Error checking market status: {str(e)}")
            return True  # Assume open if can't determine
