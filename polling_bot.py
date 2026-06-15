"""
polling_bot.py — Run the Telegram bot in polling mode (no webhook/URL needed).
Use this on VPS: python3 polling_bot.py
"""
import os
import sys
import json
import logging
 
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
 
# Load token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    try:
        with open("fyers_config.json") as f:
            TOKEN = json.load(f).get("telegram_bot_token", "")
    except Exception:
        pass
 
if not TOKEN or TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
    sys.exit("[FATAL] Set TELEGRAM_BOT_TOKEN env var")
 
from telegram import Update
from telegram.ext import Application, CommandHandler
 
# Import handlers from bot_server
from bot_server import (
    start, status, get_range, get_option,
    get_prediction, get_trade_signal
)
 
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         start))
    app.add_handler(CommandHandler("status",       status))
    app.add_handler(CommandHandler("range",        get_range))
    app.add_handler(CommandHandler("option",       get_option))
    app.add_handler(CommandHandler("predict",      get_prediction))
    app.add_handler(CommandHandler("trade_signal", get_trade_signal))
 
    print("✅ Bot running in polling mode. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
 
if __name__ == "__main__":
    main()
 
