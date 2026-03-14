# Changelog

## [Unreleased]
### Added
- ai_analyzer.py — LLM анализатор новостей с записью impact_* полей. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- ai_config.py — конфигурация LLM/логов/лимитов. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- llm_client.py — гибридный клиент local/cloud (Ollama + OpenAI/Mistral/DeepSeek). Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- prompts/analyzer.txt — системный промпт с JSON-выходом. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- scripts/check_local_models.py — скан локальных моделей. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- scripts/download_models.py — загрузка моделей с проверкой SHA256. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- run_pipeline.bat — запуск scraper + analyzer. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.

### Changed
- run.bat — теперь вызывает run_pipeline.bat. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- scraper.py — fallback на RSS content для full_text, не перезаписывать при падении Jina, smoke_test использует RSS‑богатые источники. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.

### Added
- bot/* — модульная структура Telegram бота (aiogram 3.x). Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- broadcaster.py — рассылка новых новостей подписчикам. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- validator.py — проверка токенов/БД/таблиц. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- run_bot.bat — запуск бота. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- DEPLOY_CLOUDFLARE.md — заметки по Cloudflare. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.

### Changed
- requirements.txt — добавлен aiogram 3.26.0. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.

### Added
- cf_worker/* — Cloudflare Workers (grammY + D1) бот: webhook + broadcaster + D1 схема. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- cf_worker/DEPLOY.md — деплой под Cloudflare Workers. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- cf_worker/schema.sql — D1 схема (users/items/deliveries). Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- cf_worker/run_worker.bat — локальный запуск wrangler dev. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.


### Changed
- bot/middlewares/rate_limit.py — импорт CancelHandler исправлен под aiogram 3.x. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- bot/main.py — обновлён инициализатор Bot через DefaultBotProperties. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.


### Added
- cf_worker/src/services/ingest.ts — ingestion endpoint to upsert items into D1. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- scripts/push_to_worker.py — отправка проанализированных новостей в Cloudflare Workers D1. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.

### Changed
- cf_worker/src/index.ts — добавлен /ingest endpoint с секретом. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- cf_worker/DEPLOY.md — добавлены инструкции для INGEST_SECRET и INGEST_URL. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- .env.example — заменён токен на плейсхолдер и добавлены INGEST_* переменные. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.
- run_pipeline.bat — добавлен шаг push_to_worker.py. Роль: Архитектор и инженер ботов. Дата: 2026-03-14.


### Changed
- ai_config.py — добавлен OpenRouter (base_url + model) в fallback. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- llm_client.py — добавлен OpenRouter провайдер. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.
- .env.example — добавлены OPENROUTER_* переменные. Роль: AI & Local LLM Engineer. Дата: 2026-03-14.

### Added
- cf_worker/src/utils/i18n.ts — i18n тексты и лейблы для RU/EN. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/src/keyboards/lang.ts — клавиатура выбора языка. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/src/services/translate.ts — перевод английских полей новости в русский через OpenRouter. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/migrations/2026_03_15_add_language.sql — миграция language в users. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.

### Changed
- cf_worker/src/bot.ts — выбор языка (RU/EN), локализация ответов, перевод новостей при выдаче. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/src/services/users.ts — добавлены language и профиль пользователя. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/src/services/broadcast.ts — локализация и перевод в рассылке. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/src/utils/text.ts — форматирование сообщений с лейблами. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/schema.sql — добавлен столбец language. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/DEPLOY.md — добавлены инструкции по OpenRouter и webhook secret в URL. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- cf_worker/.dev.vars — синхронизация переменных окружения для wrangler dev. Роль: DevOps инженер и специалист по CI/CD. Дата: 2026-03-15.
- .gitignore — добавлены секреты и локальные артефакты. Роль: DevOps инженер и специалист по CI/CD. Дата: 2026-03-15.
- cf_worker/wrangler.toml — cron изменён на ежечасный. Роль: DevOps инженер и специалист по CI/CD. Дата: 2026-03-15.
- ai_analyzer.py — жёсткая нормализация impact_score (1–5), очистка текста, ограничение длины action_items и rationale. Роль: AI & Local LLM Engineer. Дата: 2026-03-15.
- prompts/analyzer.txt — строгий JSON c impact_score 1–5, только русский текст, без код-блоков. Роль: AI & Local LLM Engineer. Дата: 2026-03-15.
- cf_worker/src/utils/text.ts — clamp impact_score 1–5, удаление код-блоков, лимиты длины. Роль: Архитектор и инженер ботов. Дата: 2026-03-15.
- .github/workflows/pipeline.yml — CI ingest pipeline (scrape → analyze → push). Роль: DevOps инженер и специалист по CI/CD. Дата: 2026-03-15.

