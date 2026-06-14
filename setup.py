#!/usr/bin/env python3
"""
🚀 Quick Setup Guide for Option Range Predictor Bot
This script helps you set up the bot with NSE live data (no daily token refresh!)
"""

import os
import json
import sys

def main():
    print("=" * 70)
    print("📈 OPTION RANGE PREDICTOR BOT - SETUP GUIDE")
    print("=" * 70)
    print()
    print("✅ GOOD NEWS: You're now using NSE live data!")
    print("   ✓ No Fyers API key needed")
    print("   ✓ No daily token refresh required")
    print("   ✓ Truly LIVE data directly from NSE")
    print()
    
    # Step 1: Check if config exists
    config_file = "fyers_config.json"
    
    if os.path.exists(config_file):
        print(f"📁 Config file found: {config_file}")
        with open(config_file, "r") as f:
            config = json.load(f)
    else:
        print(f"📝 Creating config file: {config_file}")
        config = {
            "market_data_provider": "nse",
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
            "client_id": "YOUR_FYERS_CLIENT_ID_HERE",
            "secret_key": "YOUR_FYERS_SECRET_KEY_HERE",
            "redirect_uri": "http://localhost:8000/"
        }
        with open(config_file, "w") as f:
            json.dump(config, f, indent=4)
        print("✅ Config file created!")
    
    print()
    print("=" * 70)
    print("🔧 STEP 1: Install Dependencies")
    print("=" * 70)
    print("Run this command to install required packages:")
    print()
    print("  python -m pip install -r requirements.txt")
    print()
    
    print("=" * 70)
    print("📱 STEP 2: Configure Telegram Bot Token")
    print("=" * 70)
    
    current_token = config.get("telegram_bot_token", "NOT_SET")
    
    if current_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE" or current_token == "NOT_SET":
        print("⚠️  Telegram bot token is not configured!")
        print()
        print("How to get your token:")
        print("  1. Open Telegram and search for @BotFather")
        print("  2. Send /newbot command")
        print("  3. Follow the instructions")
        print("  4. Copy the token you receive")
        print()
        
        token = input("Enter your Telegram Bot Token: ").strip()
        if token:
            config["telegram_bot_token"] = token
            with open(config_file, "w") as f:
                json.dump(config, f, indent=4)
            print("✅ Token saved!")
        else:
            print("⚠️  Token not provided. You can edit fyers_config.json later.")
    else:
        print(f"✅ Token configured: {current_token[:10]}...")
    
    print()
    print("=" * 70)
    print("🎯 STEP 3: Market Data Provider")
    print("=" * 70)
    
    provider = config.get("market_data_provider", "nse")
    print(f"Current provider: {provider.upper()}")
    print()
    print("Available providers:")
    print("  • NSE (recommended) - Live, no auth needed")
    print("  • Fyers - Requires daily token refresh")
    print()
    
    change = input("Change provider? (y/n): ").strip().lower()
    if change == "y":
        print("\nChoose provider:")
        print("  1. NSE (default)")
        print("  2. Fyers")
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "2":
            config["market_data_provider"] = "fyers"
            print("⚠️  Remember: Fyers requires daily token refresh!")
            print("   Run: python fyers_auth.py")
        else:
            config["market_data_provider"] = "nse"
            print("✅ Using NSE provider (no token needed)")
        
        with open(config_file, "w") as f:
            json.dump(config, f, indent=4)
    
    print()
    print("=" * 70)
    print("🚀 STEP 4: Start the Bot")
    print("=" * 70)
    print()
    print("Run the bot with:")
    print()
    print("  python bot_server.py")
    print()
    
    print("=" * 70)
    print("📚 COMMANDS (in Telegram)")
    print("=" * 70)
    print()
    print("  /start          - Show help and available commands")
    print("  /help           - Same as /start")
    print("  /range NIFTY    - Get Nifty 50 range")
    print("  /range BANKNIFTY - Get Bank Nifty range")
    print("  /range FINNIFTY - Get Nifty Financial Services range")
    print("  /range MIDCPNIFTY - Get Nifty Midcap Select range")
    print()
    
    print("=" * 70)
    print("🔄 Switching Between Providers")
    print("=" * 70)
    print()
    print("If you want to switch providers later:")
    print()
    print("  # In Python:")
    print("  from market_data import set_provider")
    print("  set_provider('nse')    # or 'fyers'")
    print()
    print("  # Or manually edit fyers_config.json")
    print()
    
    print("=" * 70)
    print("✨ You're all set!")
    print("=" * 70)
    print()

if __name__ == "__main__":
    main()
