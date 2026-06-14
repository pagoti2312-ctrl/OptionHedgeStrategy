# Continuous Deployment Guide

This project is now prepared for a simple always-on deployment.

## Recommended options

1. Render (free/cheap, easiest for Python bots)
2. Railway
3. Any Linux VPS with systemd or Docker

## Render (recommended)

1. Push this repo to GitHub.
2. In Render, create a new Web Service.
3. Connect the repo and choose the branch.
4. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot_server.py`
5. In Environment, add any needed variables.
6. Click Deploy.

Why this works:
- Render keeps the process alive.
- The bot uses polling, so it stays online as long as the service is running.

## Railway

1. Connect the GitHub repo.
2. Create a new Python service.
3. Set Start Command to: `python bot_server.py`
4. Deploy.

## Railway

1. Connect the GitHub repo.
2. Use the default Python service.
3. Start command: `python bot_server.py`

## Docker (local or VPS)

Build:

```bash
docker build -t option-bot .
```

Run in the background:

```bash
docker run -d --name option-bot option-bot
```

Check logs:

```bash
docker logs -f option-bot
```

Stop it:

```bash
docker stop option-bot
```

## Before you deploy

1. Make sure your Telegram token is in `fyers_config.json`.
2. Verify the bot still imports:

```bash
python -c "import bot_server; print('ok')"
```

3. Keep only one bot instance running on the host.

## Important

- Duplicate polling instances cause Telegram `409 Conflict` errors.
- Use a persistent platform (Render, Railway, VPS, or Docker host), not your local laptop.
- If you want the bot to recover after a crash, use the host platform's restart-on-failure setting.
