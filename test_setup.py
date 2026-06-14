#!/usr/bin/env python3
"""
🧪 Test script to verify NSE market data provider setup
"""

import sys
import logging

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test if all required modules can be imported"""
    print("=" * 70)
    print("🔍 TEST 1: Checking imports...")
    print("=" * 70)
    
    try:
        print("  ✓ Importing numpy...", end=" ")
        import numpy
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        return False
    
    try:
        print("  ✓ Importing scipy...", end=" ")
        import scipy
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        return False
    
    try:
        print("  ✓ Importing pandas...", end=" ")
        import pandas
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        return False
    
    try:
        print("  ✓ Importing telegram...", end=" ")
        from telegram import Update
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        return False
    
    try:
        print("  ✓ Importing nsepython...", end=" ")
        import nsepython
        print("OK")
    except ImportError as e:
        print(f"FAILED: {e}")
        print("    ⚠️  Install with: pip install nsepython")
        return False
    
    return True


def test_market_data_provider():
    """Test if market data provider can be instantiated"""
    print()
    print("=" * 70)
    print("🔍 TEST 2: Testing NSE market data provider...")
    print("=" * 70)
    
    try:
        from market_data import get_provider
        print("  ✓ Importing market_data factory...", end=" ")
        print("OK")
        
        provider = get_provider("nse")
        print("  ✓ Creating NSE provider...", end=" ")
        print("OK")
        
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nse_quotes():
    """Test fetching live NSE quotes"""
    print()
    print("=" * 70)
    print("🔍 TEST 3: Fetching live NSE quotes...")
    print("=" * 70)
    
    try:
        from market_data import get_live_quotes, is_market_open
        
        print("  ℹ️  Checking if market is open...", end=" ")
        market_open = is_market_open()
        
        if not market_open:
            print("MARKET CLOSED")
            print("    ⚠️  NSE is currently closed (9:15 AM - 3:30 PM IST, Mon-Fri only)")
            print("    ℹ️  Test will still work but won't fetch real data")
        else:
            print("MARKET OPEN")
        
        print("  ✓ Fetching live quotes...", end=" ")
        quotes = get_live_quotes(["NIFTY", "VIX"])
        print("OK")
        
        if quotes["s"] == "ok":
            print("  ✓ Response status: OK")
            data = quotes.get("data", {})
            
            for symbol, quote in data.items():
                if "error" not in quote:
                    print(f"    • {symbol}:")
                    print(f"      - LTP: ₹{quote.get('ltp', 'N/A')}")
                    print(f"      - Change: {quote.get('change_pct', 'N/A')}%")
                else:
                    print(f"    ✓ {symbol} (market may be closed)")
            return True
        else:
            print(f"FAILED: {quotes.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_calculations():
    """Test date/expiry calculations"""
    print()
    print("=" * 70)
    print("🔍 TEST 4: Testing date calculations...")
    print("=" * 70)
    
    try:
        from market_data import calculate_dte, get_next_expiry
        
        for symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]:
            dte = calculate_dte(symbol)
            expiry = get_next_expiry(symbol)
            print(f"  ✓ {symbol:15} → DTE: {dte} days, Expiry: {expiry}")
        
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """Test configuration"""
    print()
    print("=" * 70)
    print("🔍 TEST 5: Checking configuration...")
    print("=" * 70)
    
    try:
        from market_data import load_config
        import os
        
        config = load_config()
        print("  ✓ Config file loaded")
        
        provider = config.get("market_data_provider", "unknown")
        print(f"  ✓ Market data provider: {provider.upper()}")
        
        token = config.get("telegram_bot_token", "NOT_SET")
        if token == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or token == "NOT_SET":
            print(f"  ⚠️  Telegram bot token: NOT CONFIGURED")
            return False
        else:
            print(f"  ✓ Telegram bot token: Configured ({token[:10]}...)")
        
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print()
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  🧪 OPTION RANGE PREDICTOR - SETUP TEST".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Market Data Provider", test_market_data_provider),
        ("NSE Quotes", test_nse_quotes),
        ("Date Calculations", test_calculations),
        ("Configuration", test_config),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ UNEXPECTED ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print()
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("=" * 70)
        print("✨ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("You're ready to run the bot:")
        print("  python bot_server.py")
        print()
        return 0
    else:
        print()
        print("=" * 70)
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        print()
        print("Fix the errors above and try again.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
