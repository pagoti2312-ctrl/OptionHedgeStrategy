"""
Minimal Flask app for deployment isolation testing.

Purpose: Determine whether the worker hang is caused by:
  1. Gunicorn / the deployment environment itself
  2. The Flask app creation
  3. Custom module imports (options_math, market_data, etc.)
  4. Module-level code in bot_server.py (config load, bot init, etc.)

If this app responds on /health, the problem is in bot_server.py.
If this app also hangs, the problem is in gunicorn or the environment.

Usage (Dockerfile CMD):
  gunicorn --bind 0.0.0.0:5000 --workers 1 --worker-class sync test_app:flask_app
"""

from flask import Flask, jsonify

flask_app = Flask(__name__)


@flask_app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "test-app"}), 200


@flask_app.route("/")
def index():
    return jsonify({
        "status": "running",
        "service": "minimal-test-app",
        "note": "No custom imports, no bot init, no async code.",
    }), 200


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=5000, debug=False)
