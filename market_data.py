"""
Market data factory - easily switch between providers (NSE, Fyers, etc.)
This wrapper maintains backward compatibility while adding flexibility.
"""
import os
import json
import logging
from nse_data_provider import NSEDataProvider
from fyers_data_provider import FyersDataProvider

logger = logging.getLogger(__name__)

CONFIG_FILE = "fyers_config.json"


def get_provider(provider_name: str = None):
    """
    Factory function to get market data provider.
    
    Args:
        provider_name: "nse" (default, recommended) or "fyers"
        
    Returns:
        MarketDataProvider instance
    """
    # Load config to check user preference
    if provider_name is None:
        config = load_config()
        provider_name = config.get("market_data_provider", "nse")
    
    provider_name = provider_name.lower()
    
    if provider_name == "nse":
        logger.info("Using NSE market data provider (live, no token refresh needed)")
        return NSEDataProvider()
    elif provider_name == "fyers":
        logger.warning("Using Fyers provider - ⚠️ requires daily token refresh")
        return FyersDataProvider()
    else:
        logger.info("Unknown provider '%s', defaulting to NSE", provider_name)
        return NSEDataProvider()


def load_config():
    """Load market data configuration"""
    if not os.path.exists(CONFIG_FILE):
        config = {
            "market_data_provider": "nse",
            "client_id": "YOUR_FYERS_CLIENT_ID_HERE",
            "secret_key": "YOUR_FYERS_SECRET_KEY_HERE",
            "redirect_uri": "http://localhost:8000/",
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE"
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        logger.info("Created config file: %s", CONFIG_FILE)
        return config
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def set_provider(provider_name: str):
    """
    Switch market data provider and save to config.
    
    Args:
        provider_name: "nse" or "fyers"
    """
    config = load_config()
    config["market_data_provider"] = provider_name.lower()
    
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    
    logger.info("Market data provider switched to: %s", provider_name)


# ============================================================================
# Legacy functions for backward compatibility with existing code
# ============================================================================

_provider = None

def get_live_quotes(symbols_list):
    """
    Backward compatible wrapper for get_live_quotes.
    
    Usage (no changes needed to existing code):
        from fyers_data import get_live_quotes
        result = get_live_quotes(['NIFTY', 'BANKNIFTY'])
    """
    global _provider
    if _provider is None:
        _provider = get_provider()
    
    return _provider.get_live_quotes(symbols_list)


def calculate_dte(index_name="NIFTY"):
    """
    Backward compatible wrapper for calculate_dte.
    
    Usage (no changes needed to existing code):
        from fyers_data import calculate_dte
        dte = calculate_dte("NIFTY")
    """
    global _provider
    if _provider is None:
        _provider = get_provider()
    
    return _provider.calculate_dte(index_name)


def get_next_expiry(index_name="NIFTY"):
    """Get next expiry date"""
    global _provider
    if _provider is None:
        _provider = get_provider()
    
    return _provider.get_next_expiry(index_name)


def get_option_chain(symbol: str, expiry: str = None):
    """Get option chain for a symbol"""
    global _provider
    if _provider is None:
        _provider = get_provider()
    
    return _provider.get_option_chain(symbol, expiry)


def is_market_open():
    """Check if market is open (only works with NSE provider)"""
    global _provider
    if _provider is None:
        _provider = get_provider()
    
    if hasattr(_provider, 'is_market_open'):
        return _provider.is_market_open()
    return True
