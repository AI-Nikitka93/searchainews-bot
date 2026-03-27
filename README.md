# SearchAInews

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-All%20Rights%20Reserved-lightgrey)

## English

**SearchAInews** is an **AI-driven Telegram bot** for developers and PMs that turns AI news into **actionable insights**.  
It reduces information overload by scoring impact and producing clear next steps instead of raw headlines.

### Architecture
- **Cloudflare Workers** run the Telegram bot and AI analysis (Workers AI).
- **D1** stores news, user settings, and delivery state.
- **Python pipeline** ingests multi-source news and normalizes it.

### Features
- **Role-based delivery**: Developer / PM / Founder.
- **AI Impact Score** (1–5) with rationale and action items.
- **Serverless & zero-cost friendly** on Cloudflare Workers.

### Quickstart (Cloudflare)
For full deployment steps, see `cf_worker/DEPLOY.md`.

1. **Deploy Worker**
```bash
cd "cf_worker"
npx wrangler d1 execute "searchainews" --file "schema.sql"
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy "src/index.ts"
```

2. **Set Telegram webhook**
```bash
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WORKER_URL>/webhook&secret_token=<WEBHOOK_SECRET>
```

### Local Pipeline (optional)
```bash
install.bat
run_scraper.bat
```

### Environment Variables
**Worker**
- `BOT_TOKEN` — Telegram bot token.
- `WEBHOOK_SECRET` — webhook validation secret.
- `APP_NAME` — bot display name.
- `DEFAULT_ROLE` — default role.
- `ALLOW_WEBHOOK_WITHOUT_SECRET` — allow insecure webhook (dev only).
- `ADMIN_CHAT_ID` — admin Telegram ID for alerts.

**Ingestion**
- `INGEST_URL` — Worker `/ingest` endpoint.
- `INGEST_SECRET` — shared secret for ingestion requests.

**Optional AI**
- `OPENROUTER_API_KEY` / `OPENROUTER_API_KEYS`
- `OPENROUTER_MODEL` / `OPENROUTER_MODELS`
- `OPENROUTER_BASE_URL` / `OPENROUTER_BASE_URLS`

### Author
Created by **Nikita** (@AI_Nikitka93).

### License
This repository is published for viewing only.
All rights reserved. No use, copying, modification, distribution, deployment,
or derivative works are allowed without the author's prior written permission.

---

## Русский

**SearchAInews** — **AI‑бот для Telegram** для разработчиков и PM, который превращает AI‑новости в **actionable insights**.  
Он снижает информационный шум за счёт impact‑оценки и понятных шагов, а не «сырого» фида новостей.

### Архитектура
- **Cloudflare Workers** — бот и AI‑анализ (Workers AI).
- **D1** — хранение новостей, пользователей и доставок.
- **Python‑конвейер** — сбор и нормализация источников.

### Возможности
- **Ролевая доставка**: Developer / PM / Founder.
- **AI Impact Score** (1–5) с обоснованием и действиями.
- **Serverless и zero‑cost friendly** на Cloudflare.

### Быстрый старт (Cloudflare)
Подробные шаги деплоя: `cf_worker/DEPLOY.md`.

1. **Деплой Worker**
```bash
cd "cf_worker"
npx wrangler d1 execute "searchainews" --file "schema.sql"
npx wrangler secret put BOT_TOKEN
npx wrangler secret put WEBHOOK_SECRET
npx wrangler deploy "src/index.ts"
```

2. **Установка webhook**
```bash
https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<WORKER_URL>/webhook&secret_token=<WEBHOOK_SECRET>
```

### Локальный сбор (опционально)
```bash
install.bat
run_scraper.bat
```

### Переменные окружения
**Worker**
- `BOT_TOKEN` — токен Telegram‑бота.
- `WEBHOOK_SECRET` — секрет проверки webhook.
- `APP_NAME` — имя бота.
- `DEFAULT_ROLE` — роль по умолчанию.
- `ALLOW_WEBHOOK_WITHOUT_SECRET` — разрешить небезопасный webhook (только dev).
- `ADMIN_CHAT_ID` — Telegram ID администратора.

**Ингест**
- `INGEST_URL` — endpoint `/ingest` воркера.
- `INGEST_SECRET` — общий секрет для ingestion.

**Опционально AI**
- `OPENROUTER_API_KEY` / `OPENROUTER_API_KEYS`
- `OPENROUTER_MODEL` / `OPENROUTER_MODELS`
- `OPENROUTER_BASE_URL` / `OPENROUTER_BASE_URLS`

### Авторство
Создано **Никита** (@AI_Nikitka93).

### Лицензия
Репозиторий опубликован только для ознакомления.
Все права защищены. Любое использование, копирование, изменение,
распространение, деплой или создание производных работ запрещены без
предварительного письменного разрешения автора.
