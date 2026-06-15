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
 
    def __init__(self):
        if nsepython is None:
            raise ImportError("nsepython is required. Install with: pip install nsepython")
 
        self.expiry_weekdays = {
            "FINNIFTY":   1,
            "BANKNIFTY":  2,
            "NIFTY":      3,
            "MIDCPNIFTY": 0,
            "SENSEX":     3,
        }
 
        # Try multiple key names nsepython uses across versions
        self._ltp_keys  = ["lastPrice", "last_price", "ltp", "close", "previousClose"]
        self._open_keys = ["openPrice",  "open_price",  "open"]
        self._high_keys = ["highPrice",  "high_price",  "high"]
        self._low_keys  = ["lowPrice",   "low_price",   "low"]
        self._prev_keys = ["previousClose", "prev_close", "close"]
 
    # ── internal helpers ──────────────────────────────────────────────────────
 
    def _first(self, d: dict, keys: list, default=0.0) -> float:
        for k in keys:
            v = d.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return default
 
    def _extract_quote(self, raw) -> dict | None:
        """
        nsepython returns many shapes depending on the symbol and version:
          - {"data": {...}}
          - {"data": [{...}]}
          - {"lastPrice": ..., ...}   (flat)
          - [{"lastPrice": ...}]      (list)
        This function normalises all of them to a flat dict.
        """
        if raw is None:
            return None
 
        # Unwrap list
        if isinstance(raw, list):
            raw = raw[0] if raw else None
            if raw is None:
                return None
 
        if not isinstance(raw, dict):
            return None
 
        # Drill into nested "data" key (may be dict or list)
        inner = raw.get("data")
        if inner is not None:
            if isinstance(inner, list):
                inner = inner[0] if inner else None
            if isinstance(inner, dict):
                raw = inner
 
        return raw
 
    # ── public API ────────────────────────────────────────────────────────────
 
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
                raw  = nsepython.nse_quote(nse_sym)
                flat = self._extract_quote(raw)
 
                if flat is None:
                    logger.warning(f"No parseable data for {symbol}. Raw: {str(raw)[:200]}")
                    continue
 
                ltp = self._first(flat, self._ltp_keys)
                if ltp == 0.0:
                    logger.warning(f"LTP is 0 for {symbol}. Flat keys: {list(flat.keys())[:10]}")
                    continue
 
                quotes[symbol] = {
                    "ltp":        ltp,
                    "open":       self._first(flat, self._open_keys),
                    "high":       self._first(flat, self._high_keys),
                    "low":        self._first(flat, self._low_keys),
                    "close":      self._first(flat, self._prev_keys),
                    "change":     self._first(flat, ["change", "ch"], 0.0),
                    "change_pct": self._first(flat, ["pChange", "changepercent", "chp"], 0.0),
                }
 
            except Exception as e:
                logger.error(f"Error fetching quote for {symbol}: {e}")
 
        if not quotes:
            return {"s": "error", "message": "Failed to fetch any quotes from NSE"}
 
        return {"s": "ok", "data": quotes}
 
    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        try:
            if not expiry:
                expiry = self.get_next_expiry(symbol)
 
            nse_name_map = {
                "NIFTY":      "NIFTY",
                "BANKNIFTY":  "BANKNIFTY",
                "FINNIFTY":   "FINNIFTY",
                "MIDCPNIFTY": "MIDCPNIFTY",
                "SENSEX":     "SENSEX",
            }
            nse_sym = nse_name_map.get(symbol, symbol)
 
            chain = None
            if hasattr(nsepython, "option_chain"):
                chain = nsepython.option_chain(nse_sym)
            elif hasattr(nsepython, "nse_optionchain"):
                chain = nsepython.nse_optionchain(nse_sym, expiry)
 
            if chain:
                return {"s": "ok", "data": chain, "expiry": expiry}
            return {"s": "error", "message": f"No option chain for {symbol}"}
 
        except Exception as e:
            logger.error(f"Option chain error: {e}")
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
            now     = datetime.datetime.now()
            weekday = now.weekday()
            if weekday >= 5:
                return False
            open_  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
            close_ = now.replace(hour=15, minute=30, second=0, microsecond=0)
            return open_ <= now <= close_
        except Exception:
            return True
