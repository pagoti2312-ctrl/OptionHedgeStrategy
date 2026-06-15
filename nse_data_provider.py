"""
NSEPython-based market data provider for live NSE data.
"""
from market_data_provider import MarketDataProvider
from typing import Dict, List, Any
import datetime
import logging

logger = logging.getLogger(__name__)

try:
    import nsepython
except ImportError:
    logger.error("nsepython not installed.")
    nsepython = None


class NSEDataProvider(MarketDataProvider):

    def __init__(self):
        if nsepython is None:
            raise ImportError("nsepython is required.")
        self.expiry_weekdays = {
            "FINNIFTY": 1, "BANKNIFTY": 2, "NIFTY": 3,
            "MIDCPNIFTY": 0, "SENSEX": 3,
        }

    def _find_ltp(self, obj, depth=0, path="root") -> float | None:
        """Recursively search for any price-like key in the response."""
        if depth > 5 or obj is None:
            return None
        price_keys = ["lastPrice", "last_price", "ltp", "last", "price",
                      "close", "previousClose", "prev_close"]
        if isinstance(obj, dict):
            # Log the keys at each level so we can see structure
            logger.info(f"[NSE] {path} keys: {list(obj.keys())[:15]}")
            for k in price_keys:
                if k in obj:
                    try:
                        val = float(str(obj[k]).replace(",", ""))
                        if val > 0:
                            logger.info(f"[NSE] Found price at {path}.{k} = {val}")
                            return val
                    except (TypeError, ValueError):
                        pass
            # Recurse into nested dicts/lists
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    result = self._find_ltp(v, depth+1, f"{path}.{k}")
                    if result:
                        return result
        elif isinstance(obj, list) and obj:
            return self._find_ltp(obj[0], depth+1, f"{path}[0]")
        return None

    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        nse_name_map = {
            "NIFTY":      "NIFTY 50",
            "BANKNIFTY":  "NIFTY BANK",
            "FINNIFTY":   "NIFTY FIN SERVICE",
            "MIDCPNIFTY": "NIFTY MID SELECT",
            "VIX":        "INDIA VIX",
            "SENSEX":     "SENSEX",
        }

        quotes = {}
        for symbol in symbols_list:
            nse_sym = nse_name_map.get(symbol, symbol)
            try:
                logger.info(f"[NSE] Fetching: {nse_sym}")
                raw = nsepython.nse_quote(nse_sym)
                logger.info(f"[NSE] Raw type for {symbol}: {type(raw).__name__}")
                if isinstance(raw, dict):
                    logger.info(f"[NSE] Top-level keys for {symbol}: {list(raw.keys())[:20]}")
                elif isinstance(raw, list):
                    logger.info(f"[NSE] List length for {symbol}: {len(raw)}")
                    if raw:
                        logger.info(f"[NSE] First item keys: {list(raw[0].keys())[:20] if isinstance(raw[0], dict) else type(raw[0])}")

                ltp = self._find_ltp(raw, path=symbol)

                if ltp is None:
                    logger.error(f"[NSE] Could not find LTP for {symbol}. Full raw: {str(raw)[:500]}")
                    continue

                quotes[symbol] = {
                    "ltp": ltp, "open": 0.0, "high": 0.0,
                    "low": 0.0, "close": 0.0, "change": 0.0, "change_pct": 0.0,
                }

            except Exception as e:
                logger.error(f"[NSE] Exception for {symbol}: {type(e).__name__}: {e}")

        if not quotes:
            return {"s": "error", "message": "Failed to fetch any quotes from NSE"}
        return {"s": "ok", "data": quotes}

    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        try:
            if not expiry:
                expiry = self.get_next_expiry(symbol)
            nse_map = {
                "NIFTY": "NIFTY", "BANKNIFTY": "BANKNIFTY",
                "FINNIFTY": "FINNIFTY", "MIDCPNIFTY": "MIDCPNIFTY", "SENSEX": "SENSEX",
            }
            nse_sym = nse_map.get(symbol, symbol)
            chain = None
            if hasattr(nsepython, "option_chain"):
                chain = nsepython.option_chain(nse_sym)
            elif hasattr(nsepython, "nse_optionchain"):
                chain = nsepython.nse_optionchain(nse_sym, expiry)
            if chain:
                return {"s": "ok", "data": chain, "expiry": expiry}
            return {"s": "error", "message": f"No option chain for {symbol}"}
        except Exception as e:
            return {"s": "error", "message": str(e)}

    def calculate_dte(self, symbol: str = "NIFTY") -> int:
        target = self.expiry_weekdays.get(symbol, 3)
        today  = datetime.datetime.now().date()
        days   = target - today.weekday()
        if days <= 0:
            days += 7
        return days

    def get_next_expiry(self, symbol: str = "NIFTY") -> str:
        dte  = self.calculate_dte(symbol)
        date = datetime.datetime.now().date() + datetime.timedelta(days=dte)
        return date.strftime("%d%b%Y").upper()

    def is_market_open(self) -> bool:
        try:
            now = datetime.datetime.now()
            if now.weekday() >= 5:
                return False
            open_  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
            close_ = now.replace(hour=15, minute=30, second=0, microsecond=0)
            return open_ <= now <= close_
        except Exception:
            return True
