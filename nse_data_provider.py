"""
NSE market data provider — robust against nsepython response shape changes.
Uses direct NSE API calls as fallback if nsepython fails.
"""
from market_data_provider import MarketDataProvider
from typing import Dict, List, Any
import datetime
import logging
import json
import urllib.request

logger = logging.getLogger(__name__)

try:
    import nsepython
    HAS_NSEPYTHON = True
except ImportError:
    HAS_NSEPYTHON = False
    logger.warning("nsepython not installed — using direct NSE API only")

# Direct NSE API (no auth needed, same source nsepython uses internally)
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=trade_info"
NSE_INDEX_URL = "https://www.nseindia.com/api/allIndices"


def _safe_float(val, default=0.0) -> float:
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _deep_find(obj, keys, depth=0) -> float | None:
    """Search recursively for any of the given keys in a nested structure."""
    if depth > 6 or obj is None:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                v = _safe_float(obj[k])
                if v > 0:
                    return v
        for v in obj.values():
            if isinstance(v, (dict, list)):
                result = _deep_find(v, keys, depth + 1)
                if result:
                    return result
    elif isinstance(obj, list):
        for item in obj[:3]:
            result = _deep_find(item, keys, depth + 1)
            if result:
                return result
    return None


PRICE_KEYS = [
    "lastPrice", "last_price", "ltp", "last", "price",
    "currentValue", "current", "previousClose", "prev_close", "close",
    "indexSymbol", "ltP",
]


class NSEDataProvider(MarketDataProvider):

    def __init__(self):
        self.expiry_weekdays = {
            "FINNIFTY": 1, "BANKNIFTY": 2, "NIFTY": 3,
            "MIDCPNIFTY": 0, "SENSEX": 3,
        }
        self._session_cookies = None

    # ── NSE direct API (fallback) ─────────────────────────────────────────────

    def _get_nse_cookies(self) -> dict:
        """Get session cookies from NSE homepage."""
        try:
            req = urllib.request.Request("https://www.nseindia.com", headers=NSE_HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                cookies = {}
                for header in resp.headers.get_all("Set-Cookie") or []:
                    if "=" in header:
                        k, v = header.split(";")[0].split("=", 1)
                        cookies[k.strip()] = v.strip()
                return cookies
        except Exception as e:
            logger.warning(f"Could not get NSE cookies: {e}")
            return {}

    def _nse_direct_indices(self) -> dict:
        """Fetch all index values directly from NSE allIndices API."""
        try:
            if not self._session_cookies:
                self._session_cookies = self._get_nse_cookies()

            cookie_str = "; ".join(f"{k}={v}" for k, v in self._session_cookies.items())
            headers    = {**NSE_HEADERS, "Cookie": cookie_str}
            req        = urllib.request.Request(
                "https://www.nseindia.com/api/allIndices", headers=headers
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                # data = {"data": [{"indexSymbol": "NIFTY 50", "last": 23000, ...}, ...]}
                result = {}
                name_map = {
                    "NIFTY 50":          "NIFTY",
                    "NIFTY BANK":        "BANKNIFTY",
                    "NIFTY FIN SERVICE": "FINNIFTY",
                    "NIFTY MID SELECT":  "MIDCPNIFTY",
                    "INDIA VIX":         "VIX",
                    "SENSEX":            "SENSEX",
                }
                for item in data.get("data", []):
                    sym = item.get("indexSymbol") or item.get("index", "")
                    key = name_map.get(sym)
                    if key:
                        ltp = (
                            _safe_float(item.get("last"))
                            or _safe_float(item.get("lastPrice"))
                            or _safe_float(item.get("previousClose"))
                        )
                        if ltp > 0:
                            result[key] = {
                                "ltp":        ltp,
                                "open":       _safe_float(item.get("open")),
                                "high":       _safe_float(item.get("high")),
                                "low":        _safe_float(item.get("low")),
                                "close":      _safe_float(item.get("previousClose")),
                                "change":     _safe_float(item.get("change")),
                                "change_pct": _safe_float(item.get("percentChange")),
                            }
                return result
        except Exception as e:
            logger.error(f"Direct NSE API error: {e}")
            return {}

    # ── nsepython attempt ─────────────────────────────────────────────────────

    def _try_nsepython(self, symbol: str) -> float | None:
        if not HAS_NSEPYTHON:
            return None
        nse_name_map = {
            "NIFTY":      "NIFTY 50",
            "BANKNIFTY":  "NIFTY BANK",
            "FINNIFTY":   "NIFTY FIN SERVICE",
            "MIDCPNIFTY": "NIFTY MID SELECT",
            "VIX":        "INDIA VIX",
            "SENSEX":     "SENSEX",
        }
        nse_sym = nse_name_map.get(symbol, symbol)
        try:
            raw = nsepython.nse_quote(nse_sym)
            ltp = _deep_find(raw, PRICE_KEYS)
            if ltp:
                logger.info(f"nsepython OK for {symbol}: {ltp}")
            else:
                logger.warning(f"nsepython returned no price for {symbol}. Type={type(raw).__name__} Raw={str(raw)[:300]}")
            return ltp
        except Exception as e:
            logger.warning(f"nsepython failed for {symbol}: {e}")
            return None

    # ── public interface ──────────────────────────────────────────────────────

    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        quotes = {}

        # Strategy 1: direct NSE allIndices API (most reliable)
        logger.info("Trying direct NSE allIndices API...")
        direct = self._nse_direct_indices()
        for symbol in symbols_list:
            if symbol in direct:
                quotes[symbol] = direct[symbol]
                logger.info(f"Direct NSE OK: {symbol} = {direct[symbol]['ltp']}")

        # Strategy 2: nsepython for any missing symbols
        missing = [s for s in symbols_list if s not in quotes]
        for symbol in missing:
            ltp = self._try_nsepython(symbol)
            if ltp:
                quotes[symbol] = {
                    "ltp": ltp, "open": 0.0, "high": 0.0,
                    "low": 0.0, "close": 0.0, "change": 0.0, "change_pct": 0.0,
                }

        if not quotes:
            return {"s": "error", "message": "Could not fetch quotes from NSE or nsepython"}

        still_missing = [s for s in symbols_list if s not in quotes]
        if still_missing:
            logger.warning(f"Could not fetch: {still_missing}")

        return {"s": "ok", "data": quotes}

    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        try:
            if not expiry:
                expiry = self.get_next_expiry(symbol)
            if HAS_NSEPYTHON:
                nse_map = {
                    "NIFTY": "NIFTY", "BANKNIFTY": "BANKNIFTY",
                    "FINNIFTY": "FINNIFTY", "MIDCPNIFTY": "MIDCPNIFTY",
                }
                nse_sym = nse_map.get(symbol, symbol)
                fn = getattr(nsepython, "option_chain",
                     getattr(nsepython, "nse_optionchain", None))
                if fn:
                    chain = fn(nse_sym)
                    if chain:
                        return {"s": "ok", "data": chain, "expiry": expiry}
            return {"s": "error", "message": "Option chain unavailable"}
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
            # IST = UTC + 5:30 (Railway servers run on UTC)
            ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
            now = datetime.datetime.now(ist)
            if now.weekday() >= 5:
                return False
            open_  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
            close_ = now.replace(hour=15, minute=30, second=0, microsecond=0)
            return open_ <= now <= close_
        except Exception:
            return True
