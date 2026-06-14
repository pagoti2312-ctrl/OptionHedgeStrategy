"""
Abstract base class for market data providers.
Allows easy switching between Fyers, NSEPython, Upstox, etc.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any
import datetime


class MarketDataProvider(ABC):
    """Abstract interface for market data providers"""
    
    @abstractmethod
    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        """
        Fetch live market quotes for a list of symbols.
        
        Args:
            symbols_list: List of symbols (provider-specific format)
            
        Returns:
            {
                "s": "ok" or "error",
                "data": {
                    "SYMBOL": {
                        "ltp": float,
                        "open": float,
                        "high": float,
                        "low": float,
                        "close": float,
                        "change": float,
                        "change_pct": float
                    }
                },
                "message": str (if error)
            }
        """
        pass
    
    @abstractmethod
    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        """
        Fetch option chain data for a symbol.
        
        Args:
            symbol: Symbol name (e.g., "NIFTY", "BANKNIFTY")
            expiry: Expiry date (format varies by provider)
            
        Returns:
            Option chain data in normalized format
        """
        pass
    
    @abstractmethod
    def calculate_dte(self, symbol: str = "NIFTY") -> int:
        """
        Calculate days to expiry for the next standard weekly expiry.
        
        Args:
            symbol: Index name
            
        Returns:
            Days remaining to expiry (integer)
        """
        pass
    
    @abstractmethod
    def get_next_expiry(self, symbol: str = "NIFTY") -> str:
        """
        Get the next standard weekly expiry date.
        
        Args:
            symbol: Index name
            
        Returns:
            Expiry date in "DDMMMYYYY" format (e.g., "14JUN2024")
        """
        pass
