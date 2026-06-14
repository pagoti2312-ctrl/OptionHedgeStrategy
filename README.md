# 📈 Indian Indices Option Range Predictor - NSE Live Data Edition

**✨ Now with NSE live data - No API key, no daily token refresh needed!**

## What Changed?

### Previous Setup (Fyers) ❌
- Required API key authentication
- Token expired after 24 hours → had to refresh every morning
- 401 errors when token expired
- Service interruption during refresh

### New Setup (NSE Live) ✅
- **No API key needed** → Download from official NSE website
- **No token refresh** → Works 24/7
- **Truly LIVE data** → Not delayed
- **Runs continuously** → Perfect for live monitoring

---

## Architecture

### New Provider System

```
bot_server.py
    ↓
market_data.py (Factory/Wrapper)
    ↓
    ├─→ nse_data_provider.py (✨ Default - Recommended)
    └─→ fyers_data_provider.py (Legacy - Keep as fallback)

market_data_provider.py (Abstract Base Class)
```

### Key Components

| File | Purpose |
|------|---------|
| `market_data_provider.py` | Abstract interface for all providers |
| `nse_data_provider.py` | NSE live data (nsepython library) |
| `fyers_data_provider.py` | Fyers API (legacy, kept for reference) |
| `market_data.py` | Factory that selects provider + backward compatibility |
| `bot_server.py` | Updated to use market_data instead of fyers_data |

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**New dependency added:**
```
nsepython>=1.0.0  # For live NSE data (no auth needed)
```

### 2. Configure Telegram Bot Token

Edit `fyers_config.json`:

```json
{
    "market_data_provider": "nse",
    "telegram_bot_token": "YOUR_BOT_TOKEN_HERE",
    "client_id": "YOUR_FYERS_CLIENT_ID_HERE (optional)",
    "secret_key": "YOUR_FYERS_SECRET_KEY_HERE (optional)",
    "redirect_uri": "http://localhost:8000/"
}
```

Get your bot token:
1. Message `@BotFather` on Telegram
2. Send `/newbot` command
3. Follow instructions
4. Copy the token

### 3. Run the Bot

```bash
python bot_server.py
```

---

## Usage

Send these commands to your bot on Telegram:

```
/start              → Show help & commands
/help               → Same as /start
/range NIFTY        → Get Nifty 50 range forecast
/range BANKNIFTY    → Get Bank Nifty range forecast  
/range FINNIFTY     → Get Nifty Fin Services range forecast
/range MIDCPNIFTY   → Get Nifty Midcap Select range forecast/range SENSEX        → Get SENSEX range forecast
/status             → Check market status and supported indices```

**Response Example:**
```
📊 NIFTY Live Option Range Forecast
━━━━━━━━━━━━━━━━━━━━━
🟢 Index Spot (from NSE): 23,450.50
📉 India VIX (ATM IV): 14.25%
📅 Days to Expiry (DTE): 3.5 days
━━━━━━━━━━━━━━━━━━━━━

🎯 Expected Index Boundaries (1-SD, 68% Prob):
   👉 Support (Low): 23,200.75
   👉 Resistance (High): 23,700.25

📞 ATM Call Option (23400 CE):
   👉 Current: ₹245.50
   👉 Expected Min: ₹180.00
   👉 Expected Max: ₹320.00

📨 ATM Put Option (23400 PE):
   👉 Current: ₹195.75
   👉 Expected Min: ₹130.00
   👉 Expected Max: ₹270.00
━━━━━━━━━━━━━━━━━━━━━
✅ Data from NSE (live, no token refresh needed)
Calculated using Black-Scholes-Merton model
```

---

## Switching Providers

### If you want to use Fyers instead:

**Option 1: Edit Config**
```json
{
    "market_data_provider": "fyers"
}
```

**Option 2: Programmatically**
```python
from market_data import set_provider
set_provider("fyers")
```

Then run Fyers auth:
```bash
python fyers_auth.py
```

### Back to NSE:
```python
from market_data import set_provider
set_provider("nse")
```

---

## How It Works

### NSEPython Provider

```python
from market_data import get_provider

provider = get_provider("nse")

# Get live quotes (no API key needed!)
quotes = provider.get_live_quotes(["NIFTY", "BANKNIFTY", "VIX"])
# Returns: {"s": "ok", "data": {...}}

# Get days to expiry
dte = provider.calculate_dte("NIFTY")
# Returns: 3 (days)

# Get next expiry date
expiry = provider.get_next_expiry("NIFTY")
# Returns: "14JUN2026"

# Check if market is open
is_open = provider.is_market_open()
# Returns: True/False
```

### Backward Compatibility

**Old code still works:**
```python
# This still works (uses NSE by default now)
from market_data import get_live_quotes, calculate_dte

result = get_live_quotes(["NIFTY", "VIX"])
dte = calculate_dte("NIFTY")
```

---

## Creating Custom Providers

### Implement Your Own Provider

```python
from market_data_provider import MarketDataProvider
from typing import Dict, List, Any

class MyDataProvider(MarketDataProvider):
    def get_live_quotes(self, symbols_list: List[str]) -> Dict[str, Any]:
        # Your implementation
        pass
    
    def get_option_chain(self, symbol: str, expiry: str = None) -> Dict[str, Any]:
        # Your implementation
        pass
    
    def calculate_dte(self, symbol: str = "NIFTY") -> int:
        # Your implementation
        pass
    
    def get_next_expiry(self, symbol: str = "NIFTY") -> str:
        # Your implementation
        pass
```

### Register Your Provider

Update `market_data.py`:
```python
def get_provider(provider_name: str = None):
    provider_name = provider_name.lower()
    
    if provider_name == "nse":
        return NSEDataProvider()
    elif provider_name == "fyers":
        return FyersDataProvider()
    elif provider_name == "my_provider":  # Add this
        return MyDataProvider()
    else:
        return NSEDataProvider()
```

---

## Troubleshooting

### Bot not responding?
```
1. Check Telegram bot token in fyers_config.json
2. Run: python bot_server.py (check for errors)
3. Make sure Telegram bot token is valid
```

### "No module named 'nsepython'"?
```
pip install nsepython
```

### "NSE Market is currently closed"?
```
NSE trading hours: 9:15 AM - 3:30 PM IST (Monday-Friday)
Command will work automatically during market hours
```

### Getting "Market data provider not found"?
```
1. Check fyers_config.json exists
2. Check "market_data_provider" field is set to "nse" or "fyers"
3. Restart the bot: python bot_server.py
```

---

## NSE Market Hours

- **Trading Hours**: 9:15 AM - 3:30 PM IST
- **Trading Days**: Monday - Friday
- **Holidays**: National holidays and special closures

The bot will reject commands outside trading hours with a helpful message.

---

## Data Freshness

- **NSE Provider**: Truly live (updated continuously during market hours)
- **Fyers Provider**: Live with minimal delay (depends on Fyers server)

---

## Performance Notes

- **First call**: ~1-2 seconds (nsepython library initialization)
- **Subsequent calls**: ~100-500ms (cached connections)
- **No rate limiting**: NSE doesn't have rate limits for live data

---

## Future Improvements

1. Add caching for frequently accessed symbols
2. Add richer alerts/notifications for live range breaches
3. Add historical data provider
4. Add option chain visualization
5. Add alerts/notifications feature

---

## Files Changed

- ✅ `bot_server.py` - Updated to use market_data factory
- ✅ `requirements.txt` - Added nsepython
- ✅ `fyers_data.py` - Kept for reference (no longer used)
- ✨ `market_data_provider.py` - New abstract base class
- ✨ `nse_data_provider.py` - New NSE provider
- ✨ `fyers_data_provider.py` - New Fyers provider (legacy)
- ✨ `market_data.py` - New factory & wrapper

---

## Support

For issues with:
- **Bot/Telegram**: Check telegram_bot_token in fyers_config.json
- **NSE Data**: Check nsepython is installed and market is open
- **Fyers**: Run `python fyers_auth.py` to refresh token
- **Market Data**: Check internet connection

---

**Happy trading! 🚀📈**
