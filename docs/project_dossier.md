# PROJECT DOSSIER: SearchAInews

**Дата анализа:** 2026-04-04 02:23
**Аналитик:** P-PROJECT-DOSSIER
**Путь проекта:** `m:\Projects\Bot\SearchAInews`
**Статус полноты анализа:** FULL

## 1. HUMAN SUMMARY

- Что это за проект: гибридный AI-news проект вокруг Telegram. Он собирает новости об ИИ, пытается выделить их практическую важность, а затем доставляет их в личный бот и в Telegram-канал.
- Для кого он: по README и ранним Python-частям проект начинался как бот для developers / PM / founder; текущий Cloudflare Worker уже обслуживает другие роли: `ai_specialist`, `ai_developer`, `ai_enthusiast`, `ai_beginner`.
- Какую задачу решает: снижает шум вокруг AI-новостей, превращая сырой поток из RSS/страниц/релиз-нот в краткие сообщения с impact score, объяснением "почему важно" и action items.
- Как им пользуются: пользователь открывает Telegram-бота, выбирает язык и роль, получает `/latest`, подписывается на рассылку; параллельно проект сам публикует новости в канал и поддерживает почасовой ingestion/update pipeline.
- Что в нём главное: не сам Telegram UI, а связка `сбор источников -> AI-анализ -> синхронизация в Cloudflare Worker -> персональная и канальная доставка`.

## 2. QUICK IDENTITY

- Тип проекта: application / bot platform. `CONFIRMED`
- Surface: Telegram bot + Telegram channel + background ingestion pipeline + Cloudflare Worker API. `CONFIRMED`
- Основной стек: Python (`requests`, `feedparser`, `PyYAML`, `aiogram`) + TypeScript/Cloudflare Workers (`grammy`, D1, Workers AI). `CONFIRMED`
- Основной режим запуска:
  - локально/CI для ingestion и анализа: Python pipeline. `CONFIRMED`
  - в проде для пользовательского runtime: Cloudflare Worker webhook + cron. `CONFIRMED`
- Главные точки входа:
  - `scraper.py`
  - `ai_analyzer.py`
  - `scripts/push_to_worker.py`
  - `cf_worker/src/index.ts`
  - `bot/main.py` (legacy/local runtime)

## 3. SYSTEM CONTEXT

- Пользователи / акторы:
  - Telegram-пользователь бота. `CONFIRMED`
  - Telegram-канал как публичный выходной surface. `CONFIRMED`
  - Администратор, который получает freshness/broadcast alerts в Telegram. `CONFIRMED`
  - GitHub Actions scheduler. `CONFIRMED`
  - Cloudflare cron trigger. `CONFIRMED`
- Внешние системы:
  - Telegram Bot API. `CONFIRMED`
  - Cloudflare Workers, D1, Workers AI. `CONFIRMED`
  - OpenRouter для перевода и как один из cloud LLM backend-ов. `CONFIRMED`
  - Ollama / Mistral / DeepSeek / OpenAI как fallback-LLM варианты в локальном анализаторе. `CONFIRMED`
  - RSS/HTML/release-notes источники, плюс `r.jina.ai` для full-text extraction. `CONFIRMED`
- Основные входы:
  - RSS, Hacker News, Reddit, listing pages, release notes, HTML article pages. `CONFIRMED`
  - Telegram updates на `/webhook` или `/webhook/<secret>`. `CONFIRMED`
  - POST `/ingest` с уже собранными и проанализированными items. `CONFIRMED`
- Основные выходы:
  - сообщения пользователям в Telegram. `CONFIRMED`
  - посты в Telegram-канал. `CONFIRMED`
  - записи в local SQLite и remote D1. `CONFIRMED`
  - логирующие/диагностические записи и админ-алерты. `CONFIRMED`
- Главный результат работы системы: регулярно пополняемая база AI-новостей с impact-анализом и их роль-ориентированная доставка в Telegram. `CONFIRMED`

## 4. RUNTIME & OPERATION

- Как запускается:
  - локальная установка: `install.bat`. `CONFIRMED`
  - локальный scraper: `run_scraper.bat`. `CONFIRMED`
  - локальный pipeline: `run_pipeline.bat` -> `scraper.py` -> `ai_analyzer.py` -> `scripts/push_to_worker.py`. `CONFIRMED`
  - локальный aiogram bot: `run_bot.bat`. `CONFIRMED`
  - worker dev/deploy: `cf_worker/package.json` scripts `dev`, `deploy`, `db:setup`. `CONFIRMED`
- Команды dev / build / test / run:
  - `python scraper.py --config config.yaml`
  - `python ai_analyzer.py --limit 40`
  - `python scripts/push_to_worker.py --config config.yaml --limit 200`
  - `python smoke_test.py`
  - `python scripts/validate_config.py`
  - `python scripts/validate_feeds.py --config config.yaml --limit 6`
  - `python validator.py`
  - `npx wrangler dev src/index.ts`
  - `npx wrangler deploy src/index.ts`
  - `npx wrangler d1 execute AI_NEWS_DB --file schema.sql`
- Env / secrets expectations:
  - Telegram: `BOT_TOKEN`, `WEBHOOK_SECRET`, optionally `ADMIN_CHAT_ID`. `CONFIRMED`
  - ingestion bridge: `INGEST_URL`, `INGEST_SECRET`. `CONFIRMED`
  - translation/cloud inference: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`. `CONFIRMED`
  - optional cloud fallbacks for Python analyzer: `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`. `CONFIRMED`
  - optional local inference: `OLLAMA_HOST`, `OLLAMA_MODEL`. `CONFIRMED`
  - channel/news tuning vars in `cf_worker/wrangler.toml`. `CONFIRMED`
- Storage / DB / queues / cron / workers:
  - local SQLite at `${LOCALAPPDATA}/SearchAInews/data/news.db`. `CONFIRMED`
  - remote Cloudflare D1 database `searchainews`. `CONFIRMED`
  - GitHub Actions cron `15 * * * *`. `CONFIRMED`
  - Worker cron `0 * * * *`. `CONFIRMED`
  - отдельной queue нет. `CONFIRMED`
- Внешние интеграции:
  - Telegram sendMessage/webhook. `CONFIRMED`
  - Cloudflare AI model `@cf/meta/llama-3.1-8b-instruct`. `CONFIRMED`
  - `r.jina.ai` reader для enrichment отдельных источников. `CONFIRMED`

## 5. WHAT THE PROJECT ACTUALLY DOES

### CONFIRMED

- Собирает AI-новости минимум из 59 источников, описанных в `config.yaml`; это подтверждено валидатором конфигурации.  
- Поддерживает несколько типов источников: `rss`, `hackernews`, `reddit`, `release_notes`, `listing_page`.  
- Нормализует URL, фильтрует по ключевым словам и качеству контента, отсеивает семантические дубликаты, хранит state источников и hard-fail cooldown.  
- Записывает собранные items в локальный SQLite `items`.  
- Запускает LLM-анализ и дописывает `impact_score`, `impact_rationale`, `action_items_json`, `target_role`, `entities`, `confidence` в локальную БД.  
- Пушит уже scored items в Cloudflare Worker через защищённый `/ingest`.  
- Cloudflare Worker кладёт items в D1 и умеет дополнительно анализировать pending items через Workers AI, если score ещё нет.  
- Пользовательский Telegram runtime в прод-версии работает через grammY webhook в Worker, а не через polling.  
- Воркер поддерживает язык `ru`/`en`, выбор роли, меню, `/latest`, `/latest10`, `/subscribe`, `/unsubscribe`, `/about`, `/help`, `/language`, `/role`.  
- Воркер публикует обычные новости в канал батчами и умеет отдельно постить model releases / breaking items.  
- Воркер делает персональную рассылку подписанным пользователям и отмечает deliveries.  
- Воркер пишет request/webhook/bot logs в D1 и шлёт alert при stale news или проблемной рассылке.

### LIKELY

- Production truth сейчас находится именно в Cloudflare Worker, а локальный aiogram-бот остался как ранняя/резервная ветка. Это следует из README, `docs/STATE.md`, деплой-доков и того, что feature surface воркера заметно богаче локального Python-бота.  
- Python `ai_analyzer.py` используется главным образом в CI/ingestion phase, а worker `analyzePendingItems()` работает как safety net на стороне D1.  
- Канальный контент ориентирован прежде всего на русскоязычную аудиторию: `CHANNEL_LANGUAGE = "ru"`, перевод в русский встроен, summaries для канала генерируются русским системным промптом.

### UNCLEAR / NOT VERIFIED

- Не проверялся live webhook/worker URL в этом проходе, поэтому не подтверждено текущее внешнее состояние прод-инстанса.  
- Не запускался end-to-end pipeline в этой сессии, поэтому актуальная работоспособность источников, OpenRouter и remote D1 не перепроверялась.  
- `API.md` и `USER_GUIDE.md` частично отстают от кода: они описывают более ранний surface (другие роли и объёмы `/latest`), поэтому документы нельзя считать полным runtime truth.  
- Не подтверждена фактическая используемость локального aiogram-бота как поддерживаемого production path.

## 6. FEATURE MAP

| Функция / capability | Статус | Evidence |
|---|---|---|
| Сбор новостей из RSS/релиз-нот/листингов | confirmed | `scraper.py`, `config.yaml` |
| Семантический дедуп по заголовкам | confirmed | `scraper.py`, `storage.py` |
| Локальное хранение news corpus | confirmed | `storage.py`, `config.yaml` |
| AI impact-анализ локальным или cloud LLM | confirmed | `ai_analyzer.py`, `llm_client.py`, `prompts/analyzer.txt` |
| Публикация scored items в Cloudflare Worker | confirmed | `scripts/push_to_worker.py`, `cf_worker/src/index.ts`, `cf_worker/src/services/ingest.ts` |
| Telegram bot через Cloudflare webhook | confirmed | `cf_worker/src/index.ts`, `cf_worker/src/bot.ts` |
| Локальный Telegram bot через aiogram polling | confirmed | `bot/main.py`, `run_bot.bat` |
| Роли пользователей | confirmed | текущие роли в `cf_worker/src/keyboards/role.ts`; legacy-роли в `README.md`, `bot/config.py` |
| Локализация RU/EN | confirmed | `cf_worker/src/utils/i18n.ts`, `cf_worker/src/keyboards/lang.ts` |
| Перевод англоязычных новостей на русский | confirmed | `cf_worker/src/services/translate.ts` |
| Пользовательская рассылка новых items | confirmed | `cf_worker/src/services/broadcast.ts` |
| Публикация в Telegram-канал | confirmed | `cf_worker/src/services/channel.ts`, `wrangler.toml` |
| Daily admin report по каналу | confirmed | `cf_worker/src/services/channel.ts` |
| Freshness alert при “бот молчит” | confirmed | `cf_worker/src/services/freshness.ts` |
| Полноценный web UI / SaaS панель | unclear | в дереве проекта отсутствует соответствующий surface |

## 7. ARCHITECTURE MAP

| Область / модуль | Что делает | Ключевые файлы | Notes |
|---|---|---|---|
| Ingestion config | Описывает источники, HTTP-параметры, дедуп, Jina, freshness | `config.yaml` | Главный truth для сбора |
| Local collector | Забирает источники, чистит и сохраняет raw corpus | `scraper.py`, `storage.py` | Работает с local SQLite |
| Local AI analysis | Превращает raw items в scored/actionable items | `ai_analyzer.py`, `llm_client.py`, `ai_config.py`, `prompts/analyzer.txt` | Поддерживает local Ollama и cloud fallback |
| Sync bridge | Реплицирует scored items из SQLite в Worker/D1 | `scripts/push_to_worker.py` | Хранит `sync_state.json` |
| Legacy/local bot | Aiogram polling-бот поверх SQLite | `bot/*`, `broadcaster.py`, `validator.py` | Функционально беднее worker-бота |
| Worker API shell | HTTP entrypoint, auth, routes, webhook, scheduled jobs | `cf_worker/src/index.ts`, `cf_worker/src/types.ts` | Центральный runtime production-path |
| Worker bot UX | Команды, callbacks, role/lang/menu, manual fetch | `cf_worker/src/bot.ts`, `cf_worker/src/keyboards/*`, `cf_worker/src/utils/i18n.ts`, `cf_worker/src/utils/text.ts` | Текущий пользовательский surface |
| Worker user/news services | Чтение профилей, выдача `/latest`, mark delivery | `cf_worker/src/services/users.ts`, `cf_worker/src/services/news.ts` | Есть дедуп по доменам и темам |
| Worker broadcast | Почасовая персональная рассылка | `cf_worker/src/services/broadcast.ts` | Пишет статус в `deliveries` |
| Worker channel engine | Подбор, дедуп, summary, immediate model releases, batch posting | `cf_worker/src/services/channel.ts` | Самая сложная часть runtime-логики |
| Worker AI fallback | Анализирует pending items прямо в D1 через Workers AI | `cf_worker/src/services/ai_analyzer.ts` | Бэкап к Python analyzer |
| Observability/ops | Диагностика, валидации, health reports | `scripts/validate_*`, `scripts/source_health_report.py`, `scripts/diagnose_bot.py`, `docs/STATE.md` | Операционный слой, не core product UX |

## 8. DATA & INTEGRATION FLOW

- Откуда приходят данные:
  - внешние AI news sources из `config.yaml`;
  - Telegram updates;
  - cron events GitHub Actions и Cloudflare Worker.
- Где обрабатываются:
  - raw ingestion и enrichment в Python `scraper.py`;
  - impact-анализ в `ai_analyzer.py`;
  - sync в `scripts/push_to_worker.py`;
  - user delivery / channel delivery / fallback AI / freshness внутри `cf_worker/src/*`.
- Где хранятся:
  - локально в SQLite `items`, `users`, `deliveries`;
  - удалённо в D1 `users`, `items`, `deliveries`, `webhook_logs`, `bot_errors`, `bot_events`, `request_logs`, `channel_posts`, `channel_post_keys`, `channel_report_state`.
- Куда уходят:
  - в личные Telegram сообщения;
  - в Telegram-канал;
  - в админские алерты;
  - в логи и state files under `%LOCALAPPDATA%/SearchAInews/state`.
- Какие внешние зависимости критичны:
  - Telegram Bot API;
  - Cloudflare Worker/D1;
  - доступность source feeds/pages;
  - хотя бы один LLM backend для анализа/перевода.

## 9. FILES THAT DEFINE THE PROJECT

| Файл / папка | Почему это source of truth |
|---|---|
| `README.md` | Даёт проектную идентичность и intended product framing |
| `config.yaml` | Полный truth по источникам, фильтрам и local DB path |
| `.github/workflows/pipeline.yml` | Описывает реальный hourly CI ingestion path |
| `scraper.py` | Главная логика сбора, enrichment, dedupe и source-state |
| `storage.py` | Главная схема и upsert-логика local SQLite `items` |
| `ai_analyzer.py` | Главная логика преобразования raw news в actionable news |
| `llm_client.py` | Truth по LLM backends и fallback chain |
| `cf_worker/wrangler.toml` | Truth по Cloudflare runtime vars, D1 binding и cron |
| `cf_worker/schema.sql` | Truth по remote D1 schema |
| `cf_worker/src/index.ts` | Главный HTTP/scheduled entrypoint production runtime |
| `cf_worker/src/bot.ts` | Truth по текущему Telegram user experience |
| `cf_worker/src/services/channel.ts` | Truth по логике канала, breaking/model-release и batching |
| `cf_worker/src/services/broadcast.ts` | Truth по персональной доставке |
| `docs/STATE.md` | Короткий operational snapshot текущего известного состояния |
| `docs/PROJECT_HISTORY.md` | История архитектурных решений и эволюции runtime |

## 10. DIRECTORY COVERAGE

| Зона | Статус | Что найдено | Важность |
|---|---|---|---|
| root files | reviewed | README, env template, Python pipeline, docs, bat launchers | high |
| `.github` | reviewed | один workflow `pipeline.yml` | high |
| `bot/` | reviewed | aiogram legacy/local bot, services, handlers, migrations | medium |
| `cf_worker/` | reviewed | production Worker, D1 schema, TS services, migrations | high |
| `scripts/` | reviewed | ops, validation, sync, diagnostics | medium |
| `docs/` | reviewed | state/history/changelog/research notes | medium |
| `prompts/` | reviewed | LLM system prompt для Python analyzer | high |
| `.venv/` | skipped (aggregated) | installed dependencies | low |
| `__pycache__/` | skipped (aggregated) | generated bytecode | low |
| `.wrangler/` | skipped (aggregated) | local Cloudflare runtime artifacts | low |
| `cf_worker/package-lock.json` | partial | dependency lock only, not behavioral truth | low |

## 11. AI HANDOFF

- С чего следующему агенту начать чтение:
  - если нужно понять production runtime: сначала `cf_worker/src/index.ts`, потом `cf_worker/src/bot.ts`, затем `cf_worker/src/services/channel.ts`.
  - если нужно понять ingestion quality: сначала `config.yaml`, потом `scraper.py`, затем `ai_analyzer.py`.
- Какие файлы читать первыми:
  - `README.md`
  - `docs/STATE.md`
  - `config.yaml`
  - `.github/workflows/pipeline.yml`
  - `cf_worker/wrangler.toml`
  - `cf_worker/src/index.ts`
  - `cf_worker/src/bot.ts`
  - `cf_worker/src/services/channel.ts`
- Какие assumptions уже видны:
  - production рассчитан на Cloudflare Worker + D1, а не на локальный polling bot.
  - ingestion и user delivery разделены между Python и Cloudflare.
  - current role model changed over time; старые docs не полностью отражают worker runtime.
  - проект ориентирован на русскоязычную доставку даже при англоязычных источниках.
- Что нельзя предполагать без проверки:
  - что README/User Guide всё ещё полностью соответствует коду;
  - что live pipeline и live webhook сейчас исправны;
  - что OpenRouter стабильно доступен;
  - что local aiogram bot используется в production.
- Какие зоны пока неясны:
  - текущее состояние remote D1 и Telegram webhook в момент анализа;
  - реальный уровень актуальности legacy Python bot path;
  - нужен ли ещё вообще dual-runtime или legacy path можно считать archival.
- Что уже не нужно переоткрывать заново:
  - базовую структуру repo и назначение каталогов;
  - общий путь данных `source -> SQLite -> analyze -> push -> D1 -> Telegram`;
  - различие между legacy Python bot и current Worker bot;
  - наличие 59 source definitions и hybrid LLM setup.

## 12. KNOWN UNKNOWNS

- Совпадает ли текущий production behavior с `docs/STATE.md` на 2026-04-04, не проверялось live-запросами.
- Не проверялась фактическая численность пользователей/подписчиков, контент канала и реальные payloads Telegram.
- Не подтверждалось, какие из 59 источников стабильно работают прямо сейчас; подтверждена только валидность конфигурации, не текущее здоровье каждого source.
- Не верифицировался remote deploy/migration status всех SQL migration файлов; source of truth считался `schema.sql` и код воркера.

## 13. DOSSIER SNAPSHOT

```text
PROJECT TYPE: AI news aggregation + analysis + Telegram delivery platform
MAIN SURFACE: Telegram bot + Telegram channel + Cloudflare Worker API
PRIMARY ENTRYPOINTS: scraper.py, ai_analyzer.py, scripts/push_to_worker.py, cf_worker/src/index.ts
RUNTIME MODEL: Python ingestion/analysis -> push to Cloudflare D1 -> Worker webhook/cron delivery
SOURCE-OF-TRUTH FILES: config.yaml, .github/workflows/pipeline.yml, cf_worker/wrangler.toml, cf_worker/schema.sql, cf_worker/src/index.ts, cf_worker/src/bot.ts, cf_worker/src/services/channel.ts
CONFIRMED CAPABILITIES: multi-source ingestion, AI scoring, role/language bot UX, user broadcast, channel posting, translation to Russian, freshness alerts
MAIN INTEGRATIONS: Telegram Bot API, Cloudflare Workers, D1, Workers AI, OpenRouter, Ollama, GitHub Actions, r.jina.ai
MAIN UNKNOWNS: live production state, current source health, necessity of legacy aiogram path
```
