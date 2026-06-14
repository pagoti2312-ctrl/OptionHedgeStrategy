import json, urllib.request, sys
with open('fyers_config.json') as f:
    token = json.load(f)['telegram_bot_token']
url = f'https://api.telegram.org/bot{token}/getMe'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)
        print('HTTP', r.status)
        print(json.dumps(data))
except Exception as e:
    print('ERROR', type(e).__name__, str(e))
    sys.exit(2)
