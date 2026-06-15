"""
status_server.py — Simple web status page for the bot.
Run separately: python3 status_server.py
Access: http://YOUR_DROPLET_IP:8080
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
import datetime
import json
 
def check_bot_running():
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "optionbot"],
            capture_output=True, text=True
        )
        return result.stdout.strip() == "active"
    except:
        return False
 
def get_uptime():
    try:
        result = subprocess.run(
            ["systemctl", "show", "optionbot", "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True
        )
        return result.stdout.strip().replace("ActiveEnterTimestamp=", "")
    except:
        return "Unknown"
 
class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        running = check_bot_running()
        uptime  = get_uptime()
        ist     = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now     = datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")
        # Market hours check
        now_ist    = datetime.datetime.now(ist)
        market_open = (
            now_ist.weekday() < 5 and
            now_ist.replace(hour=9, minute=15, second=0) <= now_ist <=
            now_ist.replace(hour=15, minute=30, second=0)
        )
 
        if self.path == "/health":
            body = json.dumps({"status": "ok" if running else "down"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return
 
        status_color = "#00c853" if running else "#d50000"
        status_text  = "🟢 RUNNING" if running else "🔴 STOPPED"
        market_color = "#00c853" if market_open else "#ff6f00"
        market_text  = "🟢 OPEN" if market_open else "🔴 CLOSED"
 
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Option Bot Status</title>
    <meta http-equiv="refresh" content="30">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; margin: 0; }}
        .card {{ background: #161b22; border-radius: 12px; padding: 40px;
                 max-width: 480px; width: 90%; box-shadow: 0 4px 24px #0005; }}
        h1 {{ margin: 0 0 8px; font-size: 1.4em; color: #58a6ff; }}
        .subtitle {{ color: #8b949e; font-size: 0.9em; margin-bottom: 32px; }}
        .row {{ display: flex; justify-content: space-between; align-items: center;
                padding: 14px 0; border-bottom: 1px solid #21262d; }}
        .row:last-child {{ border-bottom: none; }}
        .label {{ color: #8b949e; font-size: 0.95em; }}
        .value {{ font-weight: bold; font-size: 1em; }}
        .badge {{ padding: 4px 14px; border-radius: 20px; font-size: 0.9em; }}
        .footer {{ text-align: center; color: #8b949e; font-size: 0.8em; margin-top: 24px; }}
    </style>
</head>
<body>
<div class="card">
    <h1>📈 Option Hedge Bot</h1>
    <div class="subtitle">Indian Indices Option Range Predictor</div>
 
    <div class="row">
        <span class="label">Bot Status</span>
        <span class="value" style="color:{status_color}">{status_text}</span>
    </div>
    <div class="row">
        <span class="label">Market</span>
        <span class="value" style="color:{market_color}">{market_text}</span>
    </div>
    <div class="row">
        <span class="label">Server</span>
        <span class="value">DigitalOcean Bangalore 🇮🇳</span>
    </div>
    <div class="row">
        <span class="label">Data Source</span>
        <span class="value">NSE Live (Real-time)</span>
    </div>
    <div class="row">
        <span class="label">Running Since</span>
        <span class="value" style="font-size:0.85em">{uptime}</span>
    </div>
    <div class="row">
        <span class="label">Last Checked</span>
        <span class="value" style="font-size:0.85em">{now}</span>
    </div>
 
    <div class="footer">Auto-refreshes every 30 seconds</div>
</div>
</body>
</html>"""
 
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
 
    def log_message(self, *args):
        pass
 
if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), StatusHandler)
    print("Status page running at http://0.0.0.0:8080")
    server.serve_forever()
 
