 
import asyncio
import json
import logging
import os
 
import numpy as np
from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
 
from options_math import expected_range_statistical, bsm_price
from market_data import (
    get_live_quotes, calculate_dte, is_market_open,
    get_option_chain, get_next_expiry
)
from price_predictor import StockPricePredictor
from rl_trading_agent import RLTradingAgent
 
# ── Logging ──────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
 
# ── Config ────────────────────────────────────────────────────────────────────────
CONFIG_FILE = "fyers_config.json"
 
def load_config():
    if not os.path.exists(CONFIG_FILE):
        config = {"market_data_provider": "nse", "telegram_bot_token": ""}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return config
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)
 
config    = load_config()
BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or config.get("telegram_bot_token", "")
)
 
INDEX_MAPPING = {
    "NIFTY": "NIFTY", "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY", "MIDCPNIFTY": "MIDCPNIFTY", "SENSEX": "SENSEX"
}
 
WEBHOOK_PATH = "/telegram/webhook"
 
 
def normalize_symbol(raw: str) -> str:
    return (raw or "NIFTY").strip().upper()
 
 
# ── Telegram command handlers ─────────────────────────────────────────────────────
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "📈 *Indian Indices Option Range Predictor Bot*\n\n"
        "Live NSE data · Black-Scholes pricing\n\n"
        "*Commands*\n"
        "`/range NIFTY` — Expected range + ATM CE/PE min/max\n"
        "`/option NIFTY` — ATM option LTP + expected min/max\n"
        "`/predict NIFTY` — AI price prediction\n"
        "`/trade_signal NIFTY` — RL agent signal\n"
        "`/status` — Market open/closed\n\n"
        "Supported: NIFTY · BANKNIFTY · FINNIFTY · MIDCPNIFTY · SENSEX"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
 
 
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    open_ = is_market_open()
    icon  = "🟢" if open_ else "🔴"
    state = "Open" if open_ else "Closed"
    await update.message.reply_text(
        f"{icon} Market is *{state}*\n"
        f"Symbols: {', '.join(sorted(INDEX_MAPPING))}\n"
        f"Use `/range SYMBOL` or `/option SYMBOL`",
        parse_mode="Markdown"
    )
 
 
async def get_range(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = normalize_symbol(context.args[0] if context.args else "NIFTY")
    if symbol not in INDEX_MAPPING:
        await update.message.reply_text(f"❌ Unknown symbol. Use: {', '.join(INDEX_MAPPING)}")
        return
    if not is_market_open():
        await update.message.reply_text("🚫 Market closed. Hours: 9:15 AM – 3:30 PM IST (Mon–Fri)")
        return
 
    await update.message.reply_text(f"🔍 Fetching live data for *{symbol}*…", parse_mode="Markdown")
    res = get_live_quotes([symbol, "VIX"])
    if res["s"] == "error":
        await update.message.reply_text(f"❌ NSE error: {res['message']}")
        return
 
    quotes  = res["data"]
    spot    = quotes.get(symbol, {}).get("ltp")
    vix_ltp = quotes.get("VIX", {}).get("ltp")
    if not spot or not vix_ltp:
        await update.message.reply_text("❌ Could not fetch spot or VIX.")
        return
 
    iv  = vix_ltp / 100.0
    r   = 0.07
    dte = calculate_dte(symbol)
    T   = dte / 365.0
 
    high_spot, low_spot = expected_range_statistical(spot, iv, dte, num_std_dev=1.0)
    step       = 50 if symbol in ["FINNIFTY", "MIDCPNIFTY"] else 100
    atm_strike = round(spot / step) * step
 
    ce_current = bsm_price(spot,      atm_strike, T, r, iv, option_type='C')
    ce_min     = bsm_price(low_spot,  atm_strike, T, r, iv, option_type='C')
    ce_max     = bsm_price(high_spot, atm_strike, T, r, iv, option_type='C')
    pe_current = bsm_price(spot,      atm_strike, T, r, iv, option_type='P')
    pe_min     = bsm_price(high_spot, atm_strike, T, r, iv, option_type='P')
    pe_max     = bsm_price(low_spot,  atm_strike, T, r, iv, option_type='P')
 
    msg = (
        f"📊 *{symbol} Option Range Forecast*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Spot:      `{spot:.2f}`\n"
        f"📉 India VIX: `{vix_ltp:.2f}%`\n"
        f"📅 DTE:       `{dte:.1f} days`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Expected Range (1-SD / 68% prob)*\n"
        f"   Low:  `{low_spot:.2f}`\n"
        f"   High: `{high_spot:.2f}`\n\n"
        f"📞 *ATM Call ({atm_strike} CE)*\n"
        f"   Current: `₹{ce_current:.2f}`\n"
        f"   Min:     `₹{max(ce_min, 0.05):.2f}`\n"
        f"   Max:     `₹{ce_max:.2f}`\n\n"
        f"📨 *ATM Put ({atm_strike} PE)*\n"
        f"   Current: `₹{pe_current:.2f}`\n"
        f"   Min:     `₹{max(pe_min, 0.05):.2f}`\n"
        f"   Max:     `₹{pe_max:.2f}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Black-Scholes-Merton · NSE live data_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
 
 
async def get_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = normalize_symbol(context.args[0] if context.args else "NIFTY")
    if symbol not in INDEX_MAPPING:
        await update.message.reply_text(f"❌ Unknown symbol. Use: {', '.join(INDEX_MAPPING)}")
        return
 
    await update.message.reply_text(f"🔍 Fetching option chain for *{symbol}*…", parse_mode="Markdown")
    try:
        res     = get_live_quotes([symbol, "VIX"])
        quotes  = res.get("data", {})
        spot    = quotes.get(symbol, {}).get("ltp")
        vix_ltp = quotes.get("VIX", {}).get("ltp")
        if not spot or not vix_ltp:
            await update.message.reply_text("❌ No spot/VIX data. Market may be closed.")
            return
 
        iv     = vix_ltp / 100.0
        dte    = calculate_dte(symbol)
        T      = dte / 365.0
        expiry = get_next_expiry(symbol)
        step   = 50 if symbol in ["FINNIFTY", "MIDCPNIFTY"] else 100
        atm    = round(spot / step) * step
 
        chain  = get_option_chain(symbol, expiry)
        ce_ltp = pe_ltp = None
        if chain.get("s") == "ok":
            d    = chain.get("data", {})
            rows = []
            if isinstance(d, dict):
                rows = d.get("records", {}).get("data") or d.get("data") or []
            elif isinstance(d, list):
                rows = d
            for row in rows:
                sp = row.get("strikePrice") or row.get("strike")
                if sp and int(round(float(sp))) == atm:
                    def ltp_from(o):
                        return float(o.get("lastPrice") or o.get("ltp") or o.get("last") or 0)
                    ce_ltp = ltp_from(row.get("CE") or row.get("ce") or {})
                    pe_ltp = ltp_from(row.get("PE") or row.get("pe") or {})
                    break
 
        ce_ltp = ce_ltp or bsm_price(spot, atm, T, 0.07, iv, option_type='C')
        pe_ltp = pe_ltp or bsm_price(spot, atm, T, 0.07, iv, option_type='P')
 
        high_spot, low_spot = expected_range_statistical(spot, iv, dte, num_std_dev=1.0)
        ce_min = bsm_price(low_spot,  atm, T, 0.07, iv, option_type='C')
        ce_max = bsm_price(high_spot, atm, T, 0.07, iv, option_type='C')
        pe_min = bsm_price(high_spot, atm, T, 0.07, iv, option_type='P')
        pe_max = bsm_price(low_spot,  atm, T, 0.07, iv, option_type='P')
 
        msg = (
            f"*{symbol} ATM Option ({atm}) — Expiry {expiry}*\n"
            f"Spot: `{spot:.2f}`  IV: `{iv*100:.2f}%`  DTE: `{dte}`\n"
            f"\n*Call (CE)*\n"
            f"  • LTP: `₹{ce_ltp:.2f}`\n"
            f"  • Min: `₹{max(ce_min, 0.01):.2f}`\n"
            f"  • Max: `₹{ce_max:.2f}`\n"
            f"\n*Put (PE)*\n"
            f"  • LTP: `₹{pe_ltp:.2f}`\n"
            f"  • Min: `₹{max(pe_min, 0.01):.2f}`\n"
            f"  • Max: `₹{pe_max:.2f}`\n"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"/option error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")
 
 
async def get_prediction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = normalize_symbol(context.args[0] if context.args else "NIFTY")
    if symbol not in INDEX_MAPPING:
        await update.message.reply_text(f"❌ Unknown symbol.")
        return
    await update.message.reply_text(f"🤖 Generating AI prediction for *{symbol}*…", parse_mode="Markdown")
    try:
        res  = get_live_quotes([symbol, "VIX"])
        spot = res.get("data", {}).get(symbol, {}).get("ltp")
        if not spot:
            await update.message.reply_text("❌ No market data. Market may be closed.")
            return
        np.random.seed(42)
        history   = np.array([spot * (1 + np.random.normal(0, 0.005)) for _ in range(30)])
        predictor = StockPricePredictor(window_size=20)
        if not predictor.train(history):
            await update.message.reply_text("❌ Training failed.")
            return
        pred = predictor.predict_range(history)
        msg  = (
            f"🎯 *{symbol} AI Prediction*\n\n"
            f"📊 Current:    `₹{pred['current']:.2f}`\n"
            f"📈 Pred High:  `₹{pred['predicted_high']:.2f}`\n"
            f"📉 Pred Low:   `₹{pred['predicted_low']:.2f}`\n"
            f"🔄 Trend:      *{pred['trend']}*\n"
            f"🎲 Confidence: `{pred['confidence']:.1f}%`\n\n"
            f"⚠️ _Not trading advice._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"/predict error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")
 
 
async def get_trade_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    symbol = normalize_symbol(context.args[0] if context.args else "NIFTY")
    if symbol not in INDEX_MAPPING:
        await update.message.reply_text("❌ Unknown symbol.")
        return
    await update.message.reply_text(f"🤖 Training RL agent for *{symbol}*…", parse_mode="Markdown")
    try:
        np.random.seed(42)
        prices = np.cumsum(np.random.normal(0, 50, 100)) + 18000
        agent  = RLTradingAgent(learning_rate=0.01, gamma=0.95, epsilon=0.1)
        if not agent.train(prices, episodes=5):
            await update.message.reply_text("❌ Training failed.")
            return
        sig   = agent.generate_signal(prices)
        emoji = "🟢" if sig["signal"] == "BUY" else "🔴" if sig["signal"] == "SELL" else "⚪"
        msg   = (
            f"{emoji} *{symbol} RL Signal*\n\n"
            f"📊 Price:      `₹{sig['current_price']:.2f}`\n"
            f"🎯 Signal:     *{sig['signal']}*\n"
            f"🎲 Confidence: `{sig['confidence']:.1f}%`\n"
            f"💰 Sim Balance:`₹{sig['final_balance']:.2f}`\n\n"
            f"⚠️ _Simulated. Not real advice._"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"/trade_signal error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")
 
 
# ── Bot application (module-level, shared across gunicorn workers) ────────────────
 
_bot_app: Application | None = None
_bot_loop: asyncio.AbstractEventLoop | None = None
_webhook_registered = False
 
 
def _get_loop() -> asyncio.AbstractEventLoop:
    global _bot_loop
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        pass
    if _bot_loop and not _bot_loop.is_closed():
        return _bot_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _bot_loop = loop
    return loop
 
 
def _build_app() -> Application | None:
    if not BOT_TOKEN or BOT_TOKEN in ("YOUR_TELEGRAM_BOT_TOKEN_HERE", ""):
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot will not respond to messages.")
        return None
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         start))
    app.add_handler(CommandHandler("status",       status))
    app.add_handler(CommandHandler("range",        get_range))
    app.add_handler(CommandHandler("option",       get_option))
    app.add_handler(CommandHandler("predict",      get_prediction))
    app.add_handler(CommandHandler("trade_signal", get_trade_signal))
    return app
 
 
def _ensure_initialized():
    global _bot_app, _webhook_registered
    if _bot_app is not None:
        return
    app = _build_app()
    if app is None:
        return
    loop = _get_loop()
    loop.run_until_complete(app.initialize())
    _bot_app = app
    logger.info("✅ Telegram bot initialized (webhook mode)")
 
    # ── Register webhook URL with Telegram ────────────────────────────────────
    # Railway sets RAILWAY_PUBLIC_DOMAIN automatically, e.g. web-xyz.up.railway.app
    # You can also set WEBHOOK_BASE_URL manually in Railway → Variables
    base = (
        os.environ.get("WEBHOOK_BASE_URL")
        or (f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
            if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else None)
    )
    if base:
        webhook_url = base.rstrip("/") + WEBHOOK_PATH
        loop.run_until_complete(
            _bot_app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
        )
        logger.info(f"✅ Webhook registered: {webhook_url}")
        _webhook_registered = True
    else:
        logger.warning(
            "Webhook URL unknown. Set WEBHOOK_BASE_URL in Railway → Variables.\n"
            "Example: https://your-app.up.railway.app"
        )
 
 
# ── Flask app ─────────────────────────────────────────────────────────────────────
 
flask_app = Flask(__name__)
 
 
@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "webhook_registered": _webhook_registered}), 200
 
 
@flask_app.route("/")
def index():
    return jsonify({
        "status": "running",
        "service": "Indian Indices Option Range Predictor Bot",
        "bot_ready": _bot_app is not None,
        "webhook_registered": _webhook_registered,
        "webhook_path": WEBHOOK_PATH,
    }), 200
 
 
@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    _ensure_initialized()
    if _bot_app is None:
        return jsonify({"error": "bot not initialised — check TELEGRAM_BOT_TOKEN"}), 503
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "invalid JSON"}), 400
    loop   = _get_loop()
    update = Update.de_json(data, _bot_app.bot)
    loop.run_until_complete(_bot_app.process_update(update))
    return jsonify({"ok": True}), 200
 
 
@flask_app.route("/set_webhook")
def set_webhook_manually():
    """Call this once after deploy: https://your-app.up.railway.app/set_webhook"""
    _ensure_initialized()
    if _bot_app is None:
        return jsonify({"error": "bot not initialised"}), 503
    base = request.args.get("url") or os.environ.get("WEBHOOK_BASE_URL") or (
        f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}"
        if os.environ.get("RAILWAY_PUBLIC_DOMAIN") else None
    )
    if not base:
        return jsonify({"error": "Pass ?url=https://your-app.up.railway.app"}), 400
    webhook_url = base.rstrip("/") + WEBHOOK_PATH
    loop = _get_loop()
    loop.run_until_complete(
        _bot_app.bot.set_webhook(url=webhook_url, allowed_updates=Update.ALL_TYPES)
    )
    return jsonify({"ok": True, "webhook_url": webhook_url}), 200
 
 
# ── Init bot on startup ───────────────────────────────────────────────────────────
# This runs when gunicorn imports the module, so the webhook is set before
# the first request arrives.
_ensure_initialized()
 
 
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port, debug=False)
 
