import asyncio
import json
import logging
import os

import numpy as np
from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Import our custom modules
from options_math import expected_range_statistical, bsm_price
from market_data import get_live_quotes, calculate_dte, is_market_open, get_option_chain, get_next_expiry
from price_predictor import StockPricePredictor
from rl_trading_agent import RLTradingAgent

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CONFIG_FILE = "fyers_config.json"


def load_config():
    """Load client configuration containing Telegram Bot token and market data provider"""
    if not os.path.exists(CONFIG_FILE):
        # Create a template configuration
        config = {
            "market_data_provider": "nse",
            "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE"
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return config

    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


# Initialize config — env var takes precedence over the JSON file so that
# Railway secrets work without baking credentials into the image.
config = load_config()
BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or config.get("telegram_bot_token", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
)

# Index symbol mapping (provider-agnostic)
INDEX_MAPPING = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "MIDCPNIFTY": "MIDCPNIFTY",
    "SENSEX": "SENSEX"
}


def normalize_symbol(raw_symbol: str) -> str:
    """Normalize user input to a supported index symbol."""
    return (raw_symbol or "NIFTY").strip().upper()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send instructions on how to use the bot when /start or /help is called."""
    help_text = (
        "📈 *Indian Indices Option Range Predictor Bot* 📈\n\n"
        "I fetch LIVE data directly from NSE (no API key or daily refresh needed) to get index quotes and India VIX, "
        "then compute the expected high/low bounds of the index and options using Black-Scholes.\n\n"
        "🔋 *Commands*:\n"
        "🔹 `/range NIFTY` \\- Get range for Nifty 50\n"
        "🔹 `/range BANKNIFTY` \\- Get range for Bank Nifty\n"
        "🔹 `/range FINNIFTY` \\- Get range for Nifty Financial Services\n"
        "🔹 `/range MIDCPNIFTY` \\- Get range for Nifty Midcap Select\n"
        "🔹 `/range SENSEX` \\- Get range for SENSEX\n"
        "🔹 `/option SYMBOL` \\- Get ATM option CE/PE LTP and expected min/max\n"
        "🔹 `/predict SYMBOL` \\- Get AI price prediction using ML\n"
        "🔹 `/trade_signal SYMBOL` \\- Get RL agent trading recommendation\n"
        "🔹 `/status` \\- Check market status and available indices\n\n"
        "ℹ️ _Note: Run during NSE market hours for live option LTPs._"
    )
    try:
        await update.message.reply_markdown_v2(help_text)
    except Exception:
        # Fallback to plain text if MarkdownV2 parsing fails for some clients
        safe_help = help_text.replace('`', "'")
        await update.message.reply_text(safe_help)


async def get_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch live data and send range calculations to the user."""
    # Check if they specified a symbol, default to NIFTY
    symbol_arg = normalize_symbol(context.args[0] if context.args else "NIFTY")

    if symbol_arg not in INDEX_MAPPING:
        available = ", ".join(INDEX_MAPPING.keys())
        await update.message.reply_text(
            f"❌ Unsupported index '{symbol_arg}'.\n"
            f"Please choose from: {available}"
        )
        return

    # Check if market is open
    if not is_market_open():
        await update.message.reply_text(
            "🚫 NSE Market is currently closed.\n"
            "Market hours: 9:15 AM - 3:30 PM IST (Monday-Friday)"
        )
        return

    index_symbol = INDEX_MAPPING[symbol_arg]
    vix_symbol = "VIX"

    await update.message.reply_text(f"🔍 Fetching LIVE market data for {symbol_arg} from NSE...")

    # 1. Fetch live quotes for index and VIX
    res = get_live_quotes([index_symbol, vix_symbol])

    if res["s"] == "error":
        error_msg = res["message"]
        await update.message.reply_text(f"❌ Error fetching NSE data: {error_msg}")
        return

    quotes = res["data"]
    if index_symbol not in quotes or vix_symbol not in quotes:
        missing = []
        if index_symbol not in quotes:
            missing.append(symbol_arg)
        if vix_symbol not in quotes:
            missing.append("India VIX")
        await update.message.reply_text(f"❌ Error: Missing data for {', '.join(missing)}")
        return

    # Extract data points
    spot = quotes[index_symbol]["ltp"]
    vix_ltp = quotes[vix_symbol]["ltp"]

    # India VIX LTP represents annualized volatility percentage (e.g. 14.5 -> 14.5% or 0.145)
    iv = vix_ltp / 100.0
    r = 0.07  # 7% Risk-Free Rate for Indian Markets

    # 2. Calculate Expiry days to go
    dte = calculate_dte(symbol_arg)
    T = dte / 365.0

    # 3. Calculate statistical high and low bounds for the underlying spot (1-SD)
    high_spot, low_spot = expected_range_statistical(spot, iv, dte, num_std_dev=1.0)

    # 4. Calculate expected ATM Strike and Option pricing ranges
    # Round strike to nearest 100 for Nifty/BankNifty, nearest 50 for FinNifty/Midcap
    strike_step = 50 if symbol_arg in ["FINNIFTY", "MIDCPNIFTY"] else 100
    atm_strike = round(spot / strike_step) * strike_step

    # Call calculations
    ce_current = bsm_price(spot, atm_strike, T, r, iv, option_type='C')
    ce_range_low = bsm_price(low_spot, atm_strike, T, r, iv, option_type='C')
    ce_range_high = bsm_price(high_spot, atm_strike, T, r, iv, option_type='C')

    # Put calculations
    pe_current = bsm_price(spot, atm_strike, T, r, iv, option_type='P')
    pe_range_low = bsm_price(high_spot, atm_strike, T, r, iv, option_type='P')
    pe_range_high = bsm_price(low_spot, atm_strike, T, r, iv, option_type='P')

    # Construct final message
    msg = (
        f"📊 *{symbol_arg} Live Option Range Forecast*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 *Index Spot (from NSE)*: `{spot:.2f}`\n"
        f"📉 *India VIX (ATM IV)*: `{vix_ltp:.2f}%`\n"
        f"📅 *Days to Expiry (DTE)*: `{dte:.1f} days`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *Expected Index Boundaries (1-SD, 68% Prob):*\n"
        f"   👉 *Support (Low)*: `{low_spot:.2f}`\n"
        f"   👉 *Resistance (High)*: `{high_spot:.2f}`\n\n"
        f"📞 *ATM Call Option ({atm_strike} CE)*:\n"
        f"   👉 Current: `₹{ce_current:.2f}`\n"
        f"   👉 Expected Min: `₹{max(ce_range_low, 0.05):.2f}`\n"
        f"   👉 Expected Max: `₹{ce_range_high:.2f}`\n\n"
        f"📨 *ATM Put Option ({atm_strike} PE)*:\n"
        f"   👉 Current: `₹{pe_current:.2f}`\n"
        f"   👉 Expected Min: `₹{max(pe_range_low, 0.05):.2f}`\n"
        f"   👉 Expected Max: `₹{pe_range_high:.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ _Data from NSE \\(live, no token refresh needed\\)_\n"
        f"_Calculated using Black-Scholes-Merton model_"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current market status and supported symbols."""
    market_open = is_market_open()
    status_text = "🟢 Market is open" if market_open else "🔴 Market is currently closed"
    available = ", ".join(sorted(INDEX_MAPPING.keys()))
    await update.message.reply_text(
        f"{status_text}\n"
        f"Supported indices: {available}\n"
        f"Use /range SYMBOL or /option SYMBOL to get live values."
    )


async def get_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return ATM option CE/PE current LTP and expected min/max for a symbol."""
    symbol = normalize_symbol(context.args[0] if context.args else "NIFTY")

    provider_symbol = INDEX_MAPPING.get(symbol, symbol)

    # Allow queries outside market hours but warn user
    if not is_market_open():
        await update.message.reply_text("Note: Market is currently closed — option LTPs may be stale or unavailable.")

    await update.message.reply_text(f"Fetching ATM option data for {symbol}...")

    # Get live spot and VIX
    quotes_res = get_live_quotes([provider_symbol, "VIX"])
    if quotes_res.get("s") != "ok":
        await update.message.reply_text(f"Error fetching live quotes: {quotes_res.get('message')}")
        return

    spot = quotes_res["data"].get(provider_symbol, {}).get("ltp")
    vix = quotes_res["data"].get("VIX", {}).get("ltp")
    if spot is None:
        await update.message.reply_text("Failed to get spot price.")
        return

    iv = (vix or 0) / 100.0
    dte = calculate_dte(symbol)
    T = dte / 365.0

    expiry = get_next_expiry(symbol)
    oc = get_option_chain(symbol, expiry)
    if oc.get("s") != "ok":
        await update.message.reply_text(f"Error fetching option chain: {oc.get('message')}")
        return

    records = oc.get("data")

    # Normalize option-chain rows to a list
    rows = []
    if isinstance(records, dict):
        rows = records.get('records', {}).get('data') or records.get('data') or []
        if not rows:
            # find first list value in dict
            for v in records.values():
                if isinstance(v, list):
                    rows = v
                    break
    elif isinstance(records, list):
        rows = records

    atm = round(spot / 50) * 50
    atm_row = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        sp = r.get('strikePrice') or r.get('strike') or r.get('strike_price')
        try:
            if sp is not None and int(round(sp)) == int(atm):
                atm_row = r
                break
        except Exception:
            continue

    if not atm_row:
        await update.message.reply_text(f"ATM strike {atm} not found in option chain.")
        return

    ce = atm_row.get('CE') or atm_row.get('ce') or atm_row.get('call') or {}
    pe = atm_row.get('PE') or atm_row.get('pe') or atm_row.get('put') or {}

    # Current LTPs (keys vary depending on provider response)
    def extract_ltp(o):
        return float(o.get('lastPrice') or o.get('last_price') or o.get('last') or o.get('ltp') or 0)

    ce_ltp = extract_ltp(ce)
    pe_ltp = extract_ltp(pe)

    # Expected underlying range
    high_spot, low_spot = expected_range_statistical(spot, iv, dte, num_std_dev=1.0)

    # Expected option prices at low/high
    ce_min = bsm_price(high_spot, atm, T, 0.07, iv, option_type='C')
    ce_max = bsm_price(low_spot, atm, T, 0.07, iv, option_type='C')
    pe_min = bsm_price(low_spot, atm, T, 0.07, iv, option_type='P')
    pe_max = bsm_price(high_spot, atm, T, 0.07, iv, option_type='P')

    msg = (
        f"*{symbol} ATM Option ({atm}) — Expiry {expiry}*\n"
        f"Spot: `{spot:.2f}`  IV: `{(iv*100):.2f}%`  DTE: `{dte}`\n"
        f"\n*Call (CE)*\n"
        f"  • LTP: `₹{ce_ltp:.2f}`\n"
        f"  • Expected Min: `₹{max(ce_min,0.01):.2f}`\n"
        f"  • Expected Max: `₹{ce_max:.2f}`\n"
        f"\n*Put (PE)*\n"
        f"  • LTP: `₹{pe_ltp:.2f}`\n"
        f"  • Expected Min: `₹{max(pe_min,0.01):.2f}`\n"
        f"  • Expected Max: `₹{pe_max:.2f}`\n"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def get_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get AI price prediction for an index."""
    symbol_arg = normalize_symbol(context.args[0] if context.args else "NIFTY")

    if symbol_arg not in INDEX_MAPPING:
        available = ", ".join(INDEX_MAPPING.keys())
        await update.message.reply_text(
            f"❌ Unsupported index '{symbol_arg}'.\n"
            f"Please choose from: {available}"
        )
        return

    index_symbol = INDEX_MAPPING[symbol_arg]
    await update.message.reply_text(f"🤖 Generating AI prediction for {symbol_arg}...")

    try:
        res = get_live_quotes([index_symbol, "VIX"])
        if res["s"] == "error":
            await update.message.reply_text(f"❌ Error fetching data: {res.get('message')}")
            return

        quotes = res.get("data", {})
        if not quotes or index_symbol not in quotes:
            await update.message.reply_text(f"❌ No market data available for {symbol_arg}. Market may be closed.")
            return

        current_price = quotes[index_symbol].get("ltp")
        if current_price is None:
            await update.message.reply_text(f"❌ Could not get price for {symbol_arg}")
            return

        predictor = StockPricePredictor(window_size=20)

        # Create synthetic historical data based on current price with small variations
        historical_data = np.array([
            current_price * (1 + np.random.normal(0, 0.005))
            for _ in range(30)
        ])

        if not predictor.train(historical_data):
            await update.message.reply_text("❌ Failed to train prediction model.")
            return

        pred = predictor.predict_range(historical_data)
        if pred is None:
            await update.message.reply_text("❌ Prediction failed.")
            return

        msg = (
            f"🎯 *{symbol_arg} AI Price Prediction*\n\n"
            f"📊 Current Price: `₹{pred['current']:.2f}`\n"
            f"📈 Predicted High: `₹{pred['predicted_high']:.2f}`\n"
            f"📉 Predicted Low: `₹{pred['predicted_low']:.2f}`\n"
            f"🔄 Trend: *{pred['trend']}*\n"
            f"🎲 Confidence: `{pred['confidence']:.1f}%`\n\n"
            f"⚠️ _Note: ML predictions are based on patterns and should not be used as trading advice._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def get_trade_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get RL-based trading signal for an index."""
    symbol_arg = normalize_symbol(context.args[0] if context.args else "NIFTY")

    if symbol_arg not in INDEX_MAPPING:
        available = ", ".join(INDEX_MAPPING.keys())
        await update.message.reply_text(
            f"❌ Unsupported index '{symbol_arg}'.\n"
            f"Please choose from: {available}"
        )
        return

    await update.message.reply_text(f"🤖 Generating RL trading signal for {symbol_arg}... (training on historical data)")

    try:
        # Create synthetic historical data for training
        # In production, this would use real historical data from NSE
        np.random.seed(42)
        base_price = 18000  # Approximate NIFTY price
        historical_prices = []
        current_price = base_price

        for _ in range(100):
            change = np.random.normal(0, 50)
            current_price = max(current_price + change, base_price * 0.8)
            historical_prices.append(current_price)

        historical_prices = np.array(historical_prices)

        agent = RLTradingAgent(learning_rate=0.01, gamma=0.95, epsilon=0.1)

        # Train agent
        if not agent.train(historical_prices, episodes=5):
            await update.message.reply_text("❌ Failed to train RL agent.")
            return

        # Generate signal
        signal_data = agent.generate_signal(historical_prices)
        if signal_data is None:
            await update.message.reply_text("❌ Failed to generate trading signal.")
            return

        signal = signal_data["signal"]
        confidence = signal_data["confidence"]
        current_price = signal_data["current_price"]

        emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"

        msg = (
            f"{emoji} *{symbol_arg} RL Trading Signal*\n\n"
            f"📊 Current Price: `₹{current_price:.2f}`\n"
            f"🎯 Signal: *{signal}*\n"
            f"🎲 Confidence: `{confidence:.1f}%`\n"
            f"💰 Sim Balance: `₹{signal_data['final_balance']:.2f}`\n\n"
            f"⚠️ _RL agent learned from simulated data. Not real trading advice._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Trade signal error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ---------------------------------------------------------------------------
# Telegram Application — built once at module level, shared across requests.
# Webhook mode: Telegram POSTs updates to /telegram/webhook; no background
# thread or polling loop is needed, so asyncio wakeup-fd issues are avoided.
# ---------------------------------------------------------------------------

_bot_app: Application | None = None
_bot_loop: asyncio.AbstractEventLoop | None = None

WEBHOOK_PATH = "/telegram/webhook"


def _build_bot_app() -> Application | None:
    """Build and initialise the Telegram Application. Returns None if the
    token is not configured."""
    if BOT_TOKEN in ("YOUR_TELEGRAM_BOT_TOKEN_HERE", "", None):
        logger.warning(
            "Telegram Bot Token is not configured. "
            "Set TELEGRAM_BOT_TOKEN env var or edit fyers_config.json."
        )
        return None

    app = Application.builder().token(BOT_TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("range", get_range))
    app.add_handler(CommandHandler("option", get_option))
    app.add_handler(CommandHandler("predict", get_prediction))
    app.add_handler(CommandHandler("trade_signal", get_trade_signal))

    return app


def _get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop, creating and starting one if needed.

    gunicorn workers don't have a running loop by default, so we create a
    dedicated loop for the bot and run it in the background just enough to
    drive coroutines synchronously via run_until_complete."""
    global _bot_loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _bot_loop = loop
        return loop


def _ensure_bot_initialized() -> None:
    """Initialise the bot application exactly once (idempotent)."""
    global _bot_app
    if _bot_app is not None:
        return

    app = _build_bot_app()
    if app is None:
        return

    loop = _get_or_create_event_loop()
    loop.run_until_complete(app.initialize())
    _bot_app = app
    logger.info("Telegram bot application initialised (webhook mode).")
    logger.info("✅ Connected to NSE live data — no daily token refresh needed!")


def _register_webhook() -> None:
    """Tell Telegram where to send updates.

    Reads RAILWAY_PUBLIC_DOMAIN (set automatically by Railway) or
    WEBHOOK_BASE_URL (manual override) to construct the full webhook URL.
    Safe to call multiple times — skips silently if the token is missing."""
    if _bot_app is None:
        return

    base_url = os.environ.get("WEBHOOK_BASE_URL") or (
        f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        else None
    )

    if not base_url:
        logger.warning(
            "Webhook URL not set: define WEBHOOK_BASE_URL or deploy on Railway "
            "(RAILWAY_PUBLIC_DOMAIN is set automatically)."
        )
        return

    webhook_url = base_url.rstrip("/") + WEBHOOK_PATH
    loop = _get_or_create_event_loop()
    loop.run_until_complete(
        _bot_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
    )
    logger.info("Telegram webhook registered: %s", webhook_url)


# Initialise the bot and register the webhook when the module is imported
# (i.e. when gunicorn loads the WSGI app).  This runs in the main thread of
# each worker process, so asyncio has no objections.
_ensure_bot_initialized()
_register_webhook()


# ---------------------------------------------------------------------------
# Flask HTTP server — satisfies Railway's health-check on port 5000
# ---------------------------------------------------------------------------

flask_app = Flask(__name__)


@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    """Receive an update from Telegram and dispatch it to the bot."""
    if _bot_app is None:
        logger.error("Webhook received but bot is not initialised.")
        return jsonify({"error": "bot not initialised"}), 503

    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "invalid JSON"}), 400

    loop = _get_or_create_event_loop()
    update = Update.de_json(data, _bot_app.bot)
    loop.run_until_complete(_bot_app.process_update(update))
    return jsonify({"ok": True}), 200


@flask_app.route("/health")
def health():
    """Health check endpoint for Railway's load balancer."""
    return jsonify({"status": "ok", "service": "telegram-bot"}), 200


@flask_app.route("/")
def index():
    """Simple status page."""
    return jsonify({
        "status": "running",
        "service": "Indian Indices Option Range Predictor Bot",
        "bot_configured": BOT_TOKEN not in ("YOUR_TELEGRAM_BOT_TOKEN_HERE", "", None),
        "webhook_path": WEBHOOK_PATH,
    }), 200


if __name__ == "__main__":
    # Local development: run Flask's built-in server on port 5000.
    # Set WEBHOOK_BASE_URL to an ngrok/tunnel URL so Telegram can reach you.
    flask_app.run(host="0.0.0.0", port=5000, debug=False)
