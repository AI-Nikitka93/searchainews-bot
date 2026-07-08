# PROJECT UNIFIED REPORT: SearchAInews

**Дата анализа:** 2026-04-28 19:32
**Аналитик:** P-PROJECT-UNIFIED
**Путь проекта:** `M:\Projects\Bot\SearchAInews`
**Режим:** FULL
**Статус полноты анализа:** FULL
**Тип проекта:** гибридный Telegram news product: Python ingestion pipeline + Cloudflare Worker bot/runtime + Telegram channel publishing
**Уровень зрелости:** WORKING BUT FRAGILE
**Общий verdict:** Это уже рабочая продуктовая система с живым runtime и живым ingestion, но она остаётся хрупкой из-за split-truth между локальным кодом и production, слабых build/test guardrails и дрейфа между legacy/local и current/cloud путями.

**Supersedes:** `docs/project_dossier.md`
**Compared with previous report:** `docs/project_dossier.md` (2026-04-04)
**Delta summary:** с 2026-04-04 подтверждён живой production webhook (`/health` = 200), подтверждён успешный scheduled GitHub Actions run от 2026-04-28, подтверждено, что локальный `wrangler` всё ещё авторизован в другой Cloudflare account, а во время анализа дополнительно исправлены cwd-зависимые CLI-проверки (`validate_config`, `validate_feeds`, `push_to_worker`, `smoke_test`, `scraper`).

## 1. HUMAN SUMMARY

- Что это за проект: это AI-news система вокруг Telegram, которая собирает новости про ИИ, пытается превратить их в practical-impact сообщения и раздаёт их как в личный бот, так и в канал.
- Какова исходная идея проекта: убрать шум из AI-news потока и заменить “сырые ссылки” на короткие выводы с impact score и action items.
- Для кого он: сейчас фактический primary-аудиторный слой ориентирован на `ai_specialist`, `ai_developer`, `ai_enthusiast`, `ai_beginner`; legacy Python-ветка ещё хранит старые роли `developer / pm / founder`.
- Какую задачу решает: помогает технарям и около-техническим ролям быстро понять, что из AI-news реально влияет на стек, roadmap, интеграции и наблюдаемые риски.
- Как им пользуются: ingestion собирает corpus локально, AI-анализатор ставит score и rationale, sync-мост пушит scored items в Worker/D1, а пользователь работает через Telegram webhook-бот и получает канал/личные рассылки.
- Что в нём главное: не Telegram UI сам по себе, а связка `source coverage -> enrichment -> scoring -> D1 sync -> personalized/channel delivery`.

## 2. QUICK IDENTITY

- Surface: Telegram bot + Telegram channel + scheduled ingestion + Cloudflare Worker API. `CONFIRMED`
- Project thesis / intended outcome: developer-first AI news digest с более качественным editorial selection, чем у обычных RSS/агрегаторов. `CONFIRMED`
- Основной стек: Python (`requests`, `feedparser`, `PyYAML`, `BeautifulSoup`, `aiogram`) + TypeScript (`grammy`, Cloudflare Workers, D1, Workers AI). `CONFIRMED`
- Основной режим запуска: production user runtime живёт в Cloudflare Worker; ingestion и local corpus живут в Python pipeline. `CONFIRMED`
- Главные точки входа: `scraper.py`, `ai_analyzer.py`, `scripts/push_to_worker.py`, `cf_worker/src/index.ts`, `cf_worker/src/bot.ts`, legacy `bot/main.py`. `CONFIRMED`
- На что это похоже по зрелости: не демо и не blank scaffold; это уже связанная система с реальными внешними интеграциями, но без достаточной инженерной жёсткости для статуса `NEARLY PRODUCTIZED`. `LIKELY`

## 3. SYSTEM CONTEXT

- Пользователи / акторы:
  - Telegram-пользователь бота. `CONFIRMED`
  - Публичный Telegram-канал. `CONFIRMED`
  - Администратор, получающий health/freshness alerts. `CONFIRMED`
  - GitHub Actions scheduler. `CONFIRMED`
  - Cloudflare cron scheduler. `CONFIRMED`
- Внешние системы:
  - Telegram Bot API. `CONFIRMED`
  - Cloudflare Workers + D1 + Workers AI. `CONFIRMED`
  - OpenRouter для перевода и cloud fallback inference. `CONFIRMED`
  - Ollama / Mistral / DeepSeek / OpenAI как fallback chain локального анализатора. `CONFIRMED`
  - RSS/HTML/listing/release-note источники, плюс `r.jina.ai` для text extraction. `CONFIRMED`
- Основные входы:
  - `config.yaml` с 71 источником.
  - Telegram webhook updates.
  - POST `/ingest` со scored items.
  - GitHub Actions и Worker cron.
- Основные выходы:
  - личные Telegram-сообщения;
  - посты в канал;
  - D1/SQLite записи;
  - ops/health сигналы.
- Главный результат работы системы: curated corpus AI-news с score/rationale/actions и downstream delivery по ролям. `CONFIRMED`

## 4. RUNTIME & OPERATION

- Как запускается:
  - local scrape: `python scraper.py --config config.yaml`
  - local analyze: `python ai_analyzer.py --config config.yaml --limit N`
  - sync bridge: `python scripts/push_to_worker.py --config config.yaml`
  - legacy local bot: `python -m bot.main`
  - worker dev: `npx wrangler dev src/index.ts`
  - worker deploy: `npx wrangler deploy src/index.ts`
- Команды dev / build / test / run:
  - `scripts/validate_config.py`
  - `scripts/validate_feeds.py`
  - `smoke_test.py`
  - `scripts/diagnose_bot.py`
  - `npm exec tsc --noEmit` в `cf_worker` как intended typecheck, но сейчас он не проходит. `CONFIRMED`
- Env / secrets expectations:
  - Telegram: `BOT_TOKEN`, `WEBHOOK_SECRET`, optionally `ADMIN_CHAT_ID`
  - sync/auth: `INGEST_URL`, `INGEST_SECRET`
  - translation/cloud inference: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`
  - optional local model: `OLLAMA_HOST`, `OLLAMA_MODEL`
  - worker tuning: `CHANNEL_*`, `NEWS_*`, `STALE_NEWS_HOURS`
- Storage / DB / queues / cron / workers:
  - local SQLite: `C:\Users\admin\AppData\Local\SearchAInews\data\news.db`
  - remote D1: binding `DB` in `cf_worker/wrangler.toml`
  - GitHub Actions schedule: `15 * * * *`
  - Worker cron: `0 * * * *`
  - queue-слоя нет
- Внешние интеграции:
  - Telegram sendMessage / webhook
  - Workers AI model `@cf/meta/llama-3.1-8b-instruct`
  - OpenRouter chat completions
  - external feeds/pages/release notes
- Error handling / recovery path:
  - scraper имеет retries, cooldown, hard-disable для некоторых HTTP status, state-файл `source_state.json`
  - broadcaster/channel имеют retry на Telegram 429/5xx
  - push-синк умеет замечать stale sync-state
- Logging / observability / alerting:
  - Python analyzer пишет в `%LOCALAPPDATA%\SearchAInews\logs\app.log`
  - Worker пишет `request_logs`, `webhook_logs`, `bot_errors`, `bot_events` в D1
  - freshness/source-health алерты уходят в Telegram админу
- CI/CD / deploy path:
  - GitHub Actions реально гоняет ingest pipeline
  - прямой automated Worker deploy в workflow отсутствует
  - локальный deploy path зависит от `wrangler` auth и сейчас не выглядит надёжно связанным с production account

## 4A. REPOSITORY SIGNALS

- Git activity / last meaningful commit: последний commit в `main` — `2026-03-28` (`bad127a`, `Document recovery and deployment context`). `CONFIRMED`
- Contributor pattern: solo. `CONFIRMED`
- Tags / releases / versioning: git-тегов нет; versioning в README/package.json формальное. `CONFIRMED`
- Commit hygiene pattern: в марте была плотная и тематически связанная серия коммитов вокруг ingestion/channel/deploy; дальше работа ушла в uncommitted/local state и docs. `LIKELY`
- Caveat: repo signals помогают понять процесс, но не доказывают рабочий продукт.

## 4B. LIVE PROBE

- Статус: partial
- Что удалось реально запустить:
  - `scripts/diagnose_bot.py`
  - `scripts/validate_feeds.py`
  - `scripts/validate_config.py`
  - `scripts/push_to_worker.py --dry-run`
  - `smoke_test.py`
  - `npx wrangler whoami`
  - `npm exec tsc --noEmit` в `cf_worker`
- Какие user journeys реально пройдены:
  - production Worker `/health`
  - production debug-webhook path
  - production webhook probe без header на path-secret URL
  - scheduled ingest health через GitHub Actions latest run
  - local scrape smoke path
- Что реально сработало:
  - `getMe` и `getWebhookInfo` Telegram API вернули OK
  - production worker `https://searchainews-bot.georgaishkin.workers.dev/health` вернул `200`
  - debug webhook path вернул `200`
  - scheduled GitHub Actions run `25059467392` от `2026-04-28T14:39:52Z` завершился `success`
  - `validate_config.py` после исправления passed
  - `validate_feeds.py` после исправления passed
  - `push_to_worker.py --dry-run` после исправления отработал корректно и сообщил `No new scored items to push`
  - `smoke_test.py` после исправления passed; локальный corpus вырос до `587` items, из них `333` с `full_text`
- Что сломалось или не ответило:
  - до исправления `validate_config.py` и `smoke_test.py` падали из `docs/` из-за cwd-зависимого поиска `config.yaml`
  - `npm exec tsc --noEmit` не прошёл и показал реальные TypeScript errors в `src/bot.ts`, `src/index.ts`, `src/services/*`, `src/types.ts`
  - local `wrangler whoami` на `2026-04-28` показывает другой account: `alexaiartbel@gmail.com` / `35cf1c14e9e9c6adcb3ab43d0082ba0c`
- Какие evidence собраны: logs / HTTP responses / GitHub Actions metadata / DB counts / script output

### Было найдено

- `PRJ-001`: локальный deploy context неочевидно соответствует production Worker account.
- `PRJ-002`: runtime-check scripts были частично завязаны на текущую рабочую директорию.
- `PRJ-003`: TypeScript build gate у Worker не зелёный.
- `PRJ-004`: локальная SQLite содержит unsupported target roles (`ml_engineer`, `ops`), которых current Worker UX официально не предлагает.

### Что исправлено во время анализа

- cwd-независимое разрешение `config.yaml` добавлено в:
  - `scraper.py`
  - `smoke_test.py`
  - `scripts/push_to_worker.py`
  - `scripts/validate_config.py`
  - `scripts/validate_feeds.py`
- удалены случайно сгенерированные `.js` артефакты после неудачного `npm exec tsc`

### Что после исправления перепроверено

- `scripts/validate_config.py` -> passed
- `scripts/validate_feeds.py --limit 3` -> passed
- `scripts/push_to_worker.py --dry-run --limit 5` -> passed
- `smoke_test.py` -> passed

### Что всё ещё осталось неисправным или непроверенным

- `PRJ-001` deploy/account drift
- `PRJ-003` Worker TypeScript errors
- `PRJ-004` role taxonomy drift в локальных scored данных
- живой Telegram UX и реальное качество channel posts не были прогнаны end-to-end в реальном чате

## 5. WHAT THE PROJECT ACTUALLY DOES

### CONFIRMED

- Поддерживает multi-source AI news ingestion с 71 источником (`61 rss`, `3 release_notes`, `3 listing_page`, `4 hackernews`).  
- Сохраняет raw/enriched corpus в локальный SQLite и ведёт `source_state.json` с fail-count, cooldown и hard-disable.  
- Делает semantic/title dedupe на ingestion-слое.  
- Пытается анализировать новости через local Ollama с cloud fallback chain и сохраняет `impact_score`, `impact_rationale`, `action_items_json`, `target_role`, `entities_json`, `confidence`.  
- Пушит scored items в Cloudflare Worker `/ingest`, где данные upsert-ятся в D1.  
- Запускает user-facing Telegram runtime через Cloudflare Worker webhook, а не через polling.  
- Имеет отдельный channel layer с почасовым окном, dedupe, source-ranking, model-release bypass и daily admin report.  
- Имеет legacy aiogram bot/runtime над той же локальной SQLite, но с урезанным surface и старой роль-таксономией.  
- На `2026-04-28` production webhook жив, а scheduled pipeline прошёл успешно.  

### LIKELY

- Current production truth находится в Worker-ветке, а `bot/` — legacy/local fallback.  
- Локальные изменения в `cf_worker/src/services/channel.ts` и `cf_worker/src/services/ai_analyzer.ts` ещё не гарантированно live, потому что локальный `wrangler` авторизован не в тот аккаунт, а automated deploy в workflow нет.  
- Current editorial direction сместился в `developer-first` слой и пытается давить community/media noise в пользу official/expert sources.  

### UNCLEAR

- Насколько именно live channel уже отражает текущий локальный editorial refactor.
- Используются ли scored items с legacy roles (`ml_engineer`, `ops`) в production D1, или это только локальный исторический хвост.
- Совпадает ли remote D1 schema/state с локальной кодовой моделью channel-layer после мартовских миграций.

### NOT VERIFIED

- Реальный end-user flow `/start -> role -> latest` в production Telegram-чате.
- Реальное качество свежих channel posts после 2026-04-28 pipeline run.
- Возможность безопасно задеплоить текущие локальные правки из этой машины в production account.

## 6. CORE FLOWS

### User Flow

- Trigger: пользователь открывает бота, шлёт `/start`, выбирает язык и роль.
- Main path: `cf_worker/src/index.ts` -> `cf_worker/src/bot.ts` -> `services/users.ts` -> `services/news.ts` -> `utils/text.ts`.
- Modules involved: webhook auth, grammY bot, i18n, role keyboard, D1 reads, translation.
- Output: пользователь получает последние deduped items и они помечаются delivered.
- Confidence: `CONFIRMED` по коду, `NOT VERIFIED` живьём.
- Live test status: not_run
- Real evidence: production webhook healthy; команды и callbacks читаются из `cf_worker/src/bot.ts`.

### Admin / Operator Flow

- Trigger: hourly GitHub Actions schedule или ручной `workflow_dispatch`.
- Main path: `.github/workflows/pipeline.yml` -> `scripts/validate_config.py` -> `scraper.py` -> `ai_analyzer.py` -> `scripts/push_to_worker.py` -> optional health report / failure notify.
- Modules involved: Python pipeline, sync bridge, GitHub Actions.
- Output: свежие scored items в Worker/D1 и ops-signal при сбоях.
- Confidence: `CONFIRMED`
- Live test status: passed
- Real evidence: scheduled run `25059467392` success on `2026-04-28`.

### System / Ingestion Flow

- Trigger: local run, CI run, smoke test.
- Main path: `config.yaml` -> adapters (`rss`, `hackernews`, `reddit`, `release_notes`, `listing_page`) -> optional Jina enrichment -> local SQLite upsert -> source state update.
- Modules involved: `scraper.py`, `storage.py`, `%LOCALAPPDATA%\SearchAInews\state\source_state.json`.
- Output: raw/enriched local corpus.
- Confidence: `CONFIRMED`
- Live test status: passed
- Real evidence: `smoke_test.py` passed; corpus post-run `587` items, `333` with `full_text`.

### Delivery / Publishing Flow

- Trigger: POST `/ingest`, Worker cron, internal channel trigger.
- Main path: `cf_worker/src/index.ts` -> `services/ingest.ts` -> `services/channel.ts` / `services/broadcast.ts`.
- Modules involved: D1 upsert, candidate ranking, AI rewrite, Telegram send, `channel_posts`, `channel_post_keys`.
- Output: channel post or personal delivery plus D1 trace.
- Confidence: `CONFIRMED` по коду, `PARTIAL` по live evidence.
- Live test status: partial
- Real evidence: live worker reachable; channel/broadcast functions inspected; production send path не прогонялся в реальном чате.

### Sync / Background Jobs Flow

- Trigger: `scripts/push_to_worker.py`, Worker scheduled job.
- Main path: local SQLite scored frontier -> sync_state.json -> `/ingest` -> Worker scheduled `analyzePendingItems -> runChannelBroadcast -> runBroadcast -> checkFreshness`.
- Modules involved: `scripts/push_to_worker.py`, `cf_worker/src/index.ts`, `services/ai_analyzer.ts`, `services/freshness.ts`.
- Output: D1 synchronization + hourly automation.
- Confidence: `CONFIRMED`
- Live test status: partial
- Real evidence: dry-run succeeded; scheduled worker chain verified only in code, not full live send.

### Legacy Flow

- Trigger: `run_bot.bat` / `python -m bot.main`
- Main path: aiogram polling -> local SQLite -> `bot/services/*`
- Modules involved: `bot/handlers/*`, `bot/services/*`, `broadcaster.py`
- Output: old-style personal bot replies with `developer / pm / founder`
- Confidence: `CONFIRMED`
- Live test status: not_run
- Real evidence: code paths and launch scripts reviewed.

## 7. FEATURE MAP

| Функция / capability | Статус | Evidence |
|---|---|---|
| Multi-source AI news ingestion | confirmed | `config.yaml`, `scraper.py`, smoke test |
| Jina-based enrichment / fallback full-text | confirmed | `scraper.py` |
| Local SQLite corpus | confirmed | `storage.py`, local DB counts |
| LLM impact analysis with fallback chain | confirmed | `ai_analyzer.py`, `llm_client.py` |
| Push scored items into Worker/D1 | confirmed | `scripts/push_to_worker.py`, `/ingest` route |
| Telegram bot via Cloudflare webhook | confirmed | `cf_worker/src/index.ts`, `cf_worker/src/bot.ts`, diagnose_bot |
| Role-based latest news retrieval | confirmed | `cf_worker/src/services/news.ts` |
| RU/EN language layer | confirmed | `cf_worker/src/utils/i18n.ts`, keyboards |
| Translation to Russian | confirmed | `cf_worker/src/services/translate.ts` |
| Hourly personal broadcasts | confirmed | `cf_worker/src/services/broadcast.ts` |
| Channel publishing with dedupe/ranking | confirmed | `cf_worker/src/services/channel.ts` |
| Worker-side fallback AI analysis | confirmed | `cf_worker/src/services/ai_analyzer.ts` |
| Real visual UI beyond Telegram surfaces | not_verified | отсутствует web/front surface |
| Clean TypeScript build for Worker | not_verified | `npm exec tsc --noEmit` fails |

## 8. ARCHITECTURE MAP

| Область / модуль | Что делает | Ключевые файлы | Notes |
|---|---|---|---|
| Source registry | Источники, freshness, Jina, cooldown, thresholds | `config.yaml` | главный truth по coverage |
| Local storage | SQLite schema и upsert raw/scored corpus | `storage.py` | не равен D1 schema |
| Collector | Fetch/adapters/filter/enrich/dedupe | `scraper.py` | primary ingestion engine |
| Local AI analysis | Score/rationale/action extraction | `ai_analyzer.py`, `llm_client.py`, `prompts/analyzer.txt`, `ai_config.py` | developer-first refactor in progress |
| Sync bridge | Replicate scored items into Worker | `scripts/push_to_worker.py` | sync frontier via `sync_state.json` |
| Worker HTTP shell | `/health`, `/ingest`, `/webhook`, cron | `cf_worker/src/index.ts` | production entrypoint |
| Worker bot UX | Commands, callbacks, role/lang flow | `cf_worker/src/bot.ts`, `src/keyboards/*`, `src/utils/i18n.ts` | user-facing runtime |
| Worker retrieval | Latest item selection and delivery marking | `cf_worker/src/services/news.ts` | includes dedupe and role aliasing |
| Worker personal broadcast | Hourly user delivery | `cf_worker/src/services/broadcast.ts` | sends admin warnings on issues |
| Worker channel engine | Selection, ranking, AI rewrite, dedupe, daily report | `cf_worker/src/services/channel.ts` | current complexity center |
| Worker translation | EN -> RU rewrite of title/rationale/actions | `cf_worker/src/services/translate.ts` | OpenRouter-dependent |
| Legacy local bot | aiogram polling bot and local broadcaster | `bot/*`, `broadcaster.py`, `validator.py` | still runnable, but not primary path |

## 9. CURRENT VS LEGACY

### Current / Primary Path

- `config.yaml` + `scraper.py` + `ai_analyzer.py` + `scripts/push_to_worker.py` + `cf_worker/src/*`
- Пользовательский runtime truth: `cf_worker/src/index.ts` и `cf_worker/src/bot.ts`
- Production health truth: live Worker URL и Telegram webhook info

### Secondary / Fallback Path

- Worker-side `analyzePendingItems()` как fallback, если ingestion пришёл без score
- `scripts/diagnose_bot.py`, `scripts/source_health_report.py`, `scripts/validate_*` как ops/support layer

### Legacy / Historical Path

- `bot/` + `broadcaster.py` + `validator.py`
- Старые роли `developer / pm / founder`
- Документы `README.md`, `API.md`, `FAQ.md`, `USER_GUIDE.md` частично всё ещё описывают именно этот более ранний слой

## 10. VISUAL & DESIGN STATE

- Есть ли реальный UI / визуальный слой: полноценного web/app UI нет; есть Telegram message formatting, inline keyboards, i18n copy. `CONFIRMED`
- Есть ли единый стиль: для Telegram-слоя стиль минимальный и утилитарный; это не design system, а текстовые шаблоны. `LIKELY`
- Есть ли брендинг: да, на уровне naming/copy (`SearchAInews`, developer-first AI digest), но без полноценного visual brand kit. `CONFIRMED`
- Есть ли продуктовая упаковка: README, changelog, state/history docs есть; packaging частично честная, но docs drift заметен. `CONFIRMED`
- Responsive / mobile readiness: как отдельный UI-вопрос не применимо; surface делегирован Telegram. `LIKELY`
- Accessibility signals: отдельного accessibility-слоя нет; Telegram закрывает базовую навигацию, но код сам по себе ничего не добавляет. `UNCLEAR`
- i18n / l10n state: RU/EN тексты и language keyboard есть. `CONFIRMED`
- Какие экраны / ассеты реально изучены: `cf_worker/src/utils/text.ts`, `cf_worker/src/utils/i18n.ts`, `cf_worker/src/keyboards/*.ts`, README badges/packaging. `CONFIRMED`
- Есть ли screenshots / runtime captures как evidence: нет. `CONFIRMED`

### Сильные стороны визуального слоя

- Наличие RU/EN copy и role/lang keyboards.
- Короткие message templates уже заточены под Telegram delivery, а не под generic dump текста.
- Новый channel-layer явно пытается сделать copy developer-first, а не просто “новость + ссылка”.

### Слабые места визуального слоя

- Нет прямого визуального продукта вне Telegram.
- Нет живых screenshots/asset-based proof, поэтому зрелость presentation слоя нельзя поднимать высоко.
- Документы и реальный runtime copy местами расходятся по ролям и объёму `/latest`.

### Что не удалось подтвердить по дизайну

- Фактическое восприятие свежих production posts/личных ответов глазами пользователя.
- Реальное качество русификации и читаемость в живом Telegram интерфейсе.

## 11. DIRECTORY COVERAGE

| Папка / зона | Статус | Что найдено | Насколько важно |
|---|---|---|---|
| `.` | reviewed | root scripts, configs, docs, pipeline entrypoints | high |
| `.github/workflows` | reviewed | hourly ingest workflow | high |
| `bot/` | reviewed | legacy aiogram runtime | medium |
| `cf_worker/` | reviewed | current webhook/runtime/channel system | high |
| `scripts/` | reviewed | validation, sync, diagnostics, ops | high |
| `docs/` | reviewed | state/history/changelog/research/old dossier | medium |
| `prompts/` | reviewed | analyzer editorial contract | high |
| `.venv/` | partial | installed runtime deps only | low |
| `.wrangler/` | partial | local worker state; not representative of prod | medium |
| `__pycache__/` | skipped | generated files | low |

## 12. FILES THAT DEFINE THE PROJECT

| Файл | Роль | Почему важен |
|---|---|---|
| `README.md` | публичная идентичность | задаёт intended product framing |
| `config.yaml` | источник правды по corpus | описывает 71 source и ingestion policy |
| `scraper.py` | ingestion engine | определяет adapters, enrichment, dedupe, source state |
| `storage.py` | local corpus schema | определяет локальную SQLite truth |
| `ai_analyzer.py` | scoring engine | превращает raw corpus в actionable items |
| `llm_client.py` | inference backend router | определяет local/cloud fallback chain |
| `prompts/analyzer.txt` | editorial contract | задаёт tone и output schema анализатора |
| `.github/workflows/pipeline.yml` | operational truth | реальный scheduled ingest path |
| `scripts/push_to_worker.py` | sync bridge | передаёт scored items в Worker |
| `cf_worker/wrangler.toml` | production runtime config | cron, vars, D1 binding, channel tuning |
| `cf_worker/schema.sql` | D1 schema truth | определяет remote runtime storage |
| `cf_worker/src/index.ts` | production entrypoint | HTTP routes и scheduled flow |
| `cf_worker/src/bot.ts` | bot UX truth | команды, callbacks, roles, menu |
| `cf_worker/src/services/news.ts` | retrieval logic | выдача latest и delivery marking |
| `cf_worker/src/services/broadcast.ts` | personal delivery | hourly broadcast logic |
| `cf_worker/src/services/channel.ts` | channel editorial core | ranking, dedupe, copy generation, channel posting |
| `docs/STATE.md` | ops snapshot | краткий truth о known blockers и live state |
| `docs/PROJECT_HISTORY.md` | architectural history | помогает отделить current от legacy |

## 13. CURRENT STATE ASSESSMENT

### Что уже выглядит зрелым

- Реальная модульность по ingestion / scoring / sync / runtime / channel.
- Большое source coverage и наличие hard-fail/cooldown state.
- Production webhook на `2026-04-28` жив и не выглядит “мертвым”.
- Scheduled ingest pipeline реально выполняется и на `2026-04-28` прошёл successfully.
- Channel-layer уже не примитивный; он содержит ranking, topic dedupe и отдельный model-release path.

### Что выглядит хрупким

- `PRJ-001`: локальный deploy context на `2026-04-28` указывает на другой Cloudflare account.
- `PRJ-003`: Worker TypeScript build сейчас красный.
- current truth размазан между кодом, `docs/STATE.md`, старым dossier и production instance.
- docs/README/user-guide drift по ролям и параметрам `/latest`.
- local D1 dev state не отражает реальную production data model.

### Что выглядит сырым или недоделанным

- role taxonomy не унифицирована: current UX использует 4 AI-роли, legacy path и некоторые scored items используют другие роли.
- automated verification слаба: unit/integration tests почти отсутствуют, CI не гоняет typecheck и не деплоит Worker.
- visual/product packaging вне Telegram практически отсутствует.
- channel content history не персистится как полноценный editorial archive; есть только item ids и dedupe keys.

### Главные неизвестности

- `PRJ-005`: какой именно код сейчас реально живёт в production Worker относительно локальных diffs.
- `PRJ-006`: насколько живой D1 содержит свежие scored items именно для новых источников и новой role taxonomy.
- `PRJ-007`: насколько реальный Telegram UX и канал выглядят качественно для конечного пользователя, а не только по коду.

## 14. PRODUCT MATURITY ASSESSMENT

- Техническая зрелость: средняя. Архитектура уже многокомпонентная и практическая, но build/test/deploy дисциплина недостаточно жёсткая.
- Функциональная зрелость: средне-высокая. Система уже делает не одну фичу, а полный цикл от source ingestion до delivery.
- Визуальная зрелость: низкая-средняя. Telegram UX есть, но это не богатый интерфейс и не было живой screen-proof проверки.
- Операционная зрелость: средняя. Есть cron, alerts, diagnostics, source health, но есть deploy/account drift и слабая dev/prod parity.
- Process / delivery maturity: низкая-средняя. GitHub Actions полезен, но нет clean type gate, нет Worker deploy automation, нет уверенного release path.
- Почему выбран именно этот уровень зрелости: проект уже решает реальную задачу и имеет живой runtime, но текущие инженерные зазоры всё ещё достаточно серьёзные, чтобы любой следующий релиз или refactor легко расходился с production truth.

## 15. GROWTH AREAS

| Зона | Что можно улучшить или добавить | Почему это важно |
|---|---|---|
| `PRJ-001 Deploy Identity` | выровнять local `wrangler` account и production project ownership | иначе локальные правки не равны deployable truth |
| `PRJ-002 Role Taxonomy` | унифицировать роли в analyzer, Worker UX, docs и данных | сейчас часть scored items формально не совпадает с current runtime surface |
| `PRJ-003 Build Gate` | починить TypeScript errors и добавить typecheck в CI | иначе channel/runtime refactors легко ломают Worker |
| `PRJ-004 Docs Drift` | обновить README / API / FAQ / USER_GUIDE под current roles и команды | иначе документация вводит в заблуждение |
| `PRJ-005 Dev/Prod Data Parity` | сделать локальный Worker/D1 snapshot более репрезентативным | сейчас local wrangler state пустой и не помогает уверенной проверке |
| Channel Observability | хранить финальный channel copy и outcome, а не только `item_id`/dedupe-key | иначе editorial audit почти невозможен |
| Analyzer Coverage | добрать backlog из 533 pending items и контролировать source-specific throughput | иначе новые источники долго не доходят до delivery |
| Legacy Simplification | либо явно отмаркировать `bot/` как legacy, либо убрать дублирование | сейчас проект несёт двойную runtime-модель |

## 16. CONFIDENCE & VERIFICATION LAYER

### Verified Facts

- Production worker `/health` вернул `200` на `2026-04-28`.
- Telegram `getMe` и `getWebhookInfo` для бота вернули `ok=true` на `2026-04-28`.
- Scheduled GitHub Actions run `25059467392` от `2026-04-28` завершился `success`.
- Local `wrangler whoami` на `2026-04-28` показывает account `35cf1c14e9e9c6adcb3ab43d0082ba0c` (`alexaiartbel@gmail.com`).
- `validate_config`, `validate_feeds`, `push_to_worker --dry-run`, `smoke_test` после path-fix проходят.
- `npm exec tsc --noEmit` не проходит и выдаёт реальные TS errors.
- Локальный corpus после smoke-run: `587` items total, `54` scored, `533` pending, `333` with `full_text`.

### Strong Inferences

- Local editorial refactor ещё не гарантированно живёт в production.
- Primary product path уже Cloudflare Worker-centric, а не aiogram-centric.
- Проект намного ближе к “рабочему internal/media product” чем к концептуальному prototype, но инженерно ещё не зацементирован.

### Open Unknowns

- Точный live content канала после последнего successful ingest.
- Фактическое состояние remote D1 таблиц `channel_posts`, `channel_post_keys`, `channel_report_state`.
- Поведение реального user flow в production Telegram-чате.

### Blockers to Confirmation

- `PRJ-001`: deploy/account mismatch блокирует уверенную dev->prod проверку.
- `PRJ-003`: broken TS typecheck снижает доверие к локальному Worker snapshot.
- Нет безопасного полного e2e user/chat test без взаимодействия с живым Telegram runtime.
- Visual state не был подтверждён screenshots/runtime captures.

## 17. FINAL VERDICT

- Это уже готовый продукт или нет: **нет; основной статус — `WORKING BUT FRAGILE`**.
- Что мешает считать его готовым продуктом: deploy-truth split, красный typecheck, role/doc drift, слабые automated tests и отсутствие уверенной dev/prod parity.
- Что уже можно считать сильной стороной проекта: это не пустой каркас, а реально работающая многошаговая система с живым webhook, живым scheduled ingest и продуманным channel-selection слоем.
- Где главный потенциал роста: выровнять production truth и инженерную дисциплину вокруг уже существующего продукта, а не изобретать систему заново.

---

## 18. POST-DEPLOY RECHECK — 2026-04-28 23:59

### Что подтверждено повторно

- `VERIFIED_LIVE`: реальный `wrangler deploy` прошёл успешно; live Worker обновлён до `Version ID 8a6ead8e-627d-4f60-8f60-107205af4d7e`.
- `VERIFIED_LIVE`: `https://searchainews-bot.georgaishkin.workers.dev/health` после выката отвечает `ok`.
- `VERIFIED_LIVE`: `py scripts/diagnose_bot.py` после выката подтверждает `getMe ok=True`, `getWebhookInfo ok=True`, `pending_update_count=0`, `worker /health=200`, `debug webhook status=200`.
- `VERIFIED_LIVE`: `py scripts/send_test_message.py` после выката возвращает `sendMessage status: 200`.
- `VERIFIED_LOCAL`: `py scripts/validate_config.py` проходит; `py scripts/push_to_worker.py --config config.yaml --dry-run` возвращает `No new scored items to push`.
- `VERIFIED_LOCAL`: `npx wrangler whoami` теперь показывает правильный project account `georgaishkin@gmail.com` / `b3b247be02d9e58286eed750c6752e34`.

### Что стало яснее

- `VERIFIED_LOCAL`: главный старый deploy blocker в форме “вообще нет доступа к account проекта” снят.
- `VERIFIED_LOCAL`: для remote D1 всё ещё нужен явный `CLOUDFLARE_ACCOUNT_ID=b3b247be02d9e58286eed750c6752e34`, иначе `wrangler` подхватывает stale cached account id.
- `VERIFIED_LOCAL`: remote `wrangler d1 migrations list searchainews --remote` показывает весь пакет миграций как `to be applied`; это признак migration ledger/schema drift, а не чистой prod parity.
- `VERIFIED_LOCAL`: `npm exec tsc --noEmit` остаётся красным и продолжает снижать доверие к локальному Worker snapshot.

### Обновлённый synthesis

- Итоговый статус проекта остаётся `WORKING BUT FRAGILE`.
- Разница по сравнению с исходным unified-audit: production truth после локального deploy теперь частично подтверждена live evidence, но release robustness всё ещё ломается о `tsc` и D1 migration drift.
- Практический вывод: продукт живой и выкатываемый, но инженерная правда всё ещё слишком хрупкая для спокойного следующего релиза без дополнительной выправки.
