# Cloudflare Workers Deploy (Telegram Bot)

## Prereqs
- Node.js LTS
- Cloudflare account
- Telegram bot token (BotFather)

## 1) Install deps
```powershell
cd "m:\Projects\Bot\SearchAInews\cf_worker"
npm install
```

## 2) Login to Cloudflare
```powershell
npx wrangler login
```

## 3) Create D1 database
```powershell
npx wrangler d1 create searchainews
```
Update `database_id` in `wrangler.toml` with the ID shown by the command.

## 4) Apply schema
```powershell
npx wrangler d1 execute searchainews --file schema.sql
```

## 5) Set secrets
```powershell
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler secret put INGEST_SECRET
npx wrangler secret put OPENROUTER_API_KEY
```

Optional:
```powershell
npx wrangler secret put ADMIN_CHAT_ID
```

## 6) Deploy
```powershell
npx wrangler deploy
```

## 7) Set Telegram webhook
```powershell
$token = "<BOT_TOKEN>"
$secret = "<WEBHOOK_SECRET>"
$webhook = "https://<your-worker>.workers.dev/webhook/$secret"
$body = @{
  url = $webhook
  allowed_updates = @('message','callback_query')
} | ConvertTo-Json
Invoke-WebRequest -Method Post -Uri "https://api.telegram.org/bot$token/setWebhook" -ContentType "application/json" -Body $body
```

## 7b) Ingest endpoint
Configure local `.env` for the pipeline:
```env
INGEST_URL=https://<your-worker>.workers.dev/ingest
INGEST_SECRET=<same secret as INGEST_SECRET>
```

## 8) Cron broadcaster
The cron trigger is configured in `wrangler.toml` as `0 * * * *` (every hour).

**Channel posting logic:**
- **Model releases** (new LLM, API, etc.) — posted immediately as single posts (bypass gap)
- **Regular news** — posted as batches of 3 news per hour

## Notes
- Free Workers limits apply (requests, CPU time, memory).
- D1 free limits apply (reads/writes/storage).
- Для перевода английских новостей в русский нужен `OPENROUTER_API_KEY` и опционально `OPENROUTER_MODEL`/`OPENROUTER_BASE_URL` в `wrangler.toml` или через секреты.
