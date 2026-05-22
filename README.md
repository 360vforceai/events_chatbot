# Project S.E.E.R.

AI-powered Discord agent for Rutgers club and event discovery.

## Setup

```bash
# Bot
cd bot && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
python discord_bot/bot.py

# Web
cd web && npm install && npm run dev
```

See `.env.example` for required environment variables (`bot/.env`).

Required for the bot/API: `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `OPENAI_API_KEY`, `ADMIN_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.
