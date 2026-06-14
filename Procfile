web: python dashboard.py
worker: gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 --worker-class gthread bot_server:flask_app
