## [ТЕМА: AI News Aggregator — конкуренты и MVP]
_Последнее обновление: 2026-03-13 | Роль: AI-исследователь идей и продуктовых возможностей_
Актуально

### Ключевые конкуренты (лендинги/каналы/рассылки)
- The Rundown AI — https://www.therundown.ai/
- Ben's Bites — https://www.bensbites.com/about
- TLDR AI — https://advertise.tldr.tech/audiences/ai-professionals-and-enthusiasts/
- The Neuron — https://www.theneurondaily.com/subscribe
- Aggregaat (Telegram-бот) — https://aggregaat.bot/

### Смежные/альтернативы (боты/приложения)
- News Keeper (Telegram RSS + AI summaries) — https://www.newskeeper.io/
- Signaller (Telegram + RSS + X, AI-фильтрация/постинг) — https://signaller.pro/
- NewsBang (AI news app) — https://www.producthunt.com/products/newsbang
- Epigram (open-source AI news app) — https://www.producthunt.com/products/epigram
- Hacker News AI Newsletter — https://hackernewsai.com/

### Сигналы рынка
- Adoption signal: у крупных рассылок заявлены большие аудитории и регулярные выпуски (The Rundown, TLDR AI, The Neuron).
- Pain signal: спрос на «кратко, по делу» и экономию времени (миссии у The Rundown/The Neuron/NewsBang/News Keeper).
- Crowding signal: много рассылок и ботов с похожей механикой «дайджеста» без глубокой персонализации/impact-оценки.

### Пробелы (opportunity gaps)
- Недостаток анализа влияния на бизнес/разработку (impact, risks, roadmap).
- Слабая персонализация под роль (dev/PM/Founder).
- Нет системного «что делать дальше» (next actions).

### Что нужно перепроверить при следующем обновлении
- Новые/закрывшиеся AI-дайджесты и Telegram-каналы.
- Свежие конкуренты на Product Hunt и GitHub (последние 30 дней).
- Актуальные метрики аудиторий (числа подписчиков/OR).

## [ТЕМА: Источники для Actionable Impact — RSS/API/парсинг]
_Последнее обновление: 2026-03-14 | Роль: Инженер веб-разведки, парсинга и мониторинга_
Актуально (подтверждено самостоятельным поиском; часть RSS требует user-agent)

### Приоритетные источники (расширенный список)
- OpenAI News (RSS ссылка на странице) — https://openai.com/news/ → RSS: https://openai.com/news/rss.xml
- arXiv RSS (категории) — пример: https://rss.arxiv.org/rss/cs.ai и https://rss.arxiv.org/rss/cs.lg
- NVIDIA RSS каталог (Developer Blog / Blog / Press Room) — https://www.nvidia.com/en-us/about-nvidia/rss/
- MIT News RSS каталог (AI topic / Machine Learning topic) — https://news.mit.edu/rss
- Wired RSS список (AI feed) — https://www.wired.com/rss
- TechCrunch subscribing (общий feed) — https://techcrunch.com/subscribing/
- Hacker News API — https://hacker-news.firebaseio.com/v0/
- GitHub Releases API — https://docs.github.com/en/rest/releases/releases
- GitHub Trending RSS (community) — https://mshibanami.github.io/GitHubTrendingRSS/
- Hugging Face Trending Feed (community) — https://github.com/zernel/huggingface-trending-feed

### Бесплатные API и инструменты сбора (ключевые ограничения)
- Guardian Open Platform (developer key) — 1 call/sec, 500 calls/day, free non‑commercial.
- GNews API free — 100 requests/day, 12‑hour delay, non‑commercial only.
- NewsAPI Developer — 100 requests/day, 24‑hour delay, dev/testing only.
- Mediastack Free — до 100 calls/месяц.
- World News API Free — 50 points/day, 1 req/s, 1 concurrent req, backlink required.
- arXiv API — public API с рекомендациями по лимитам.
- GitHub Releases API — доступ к public repos без auth (есть rate limits).
- Hacker News API — public read‑only endpoints.
- r.jina.ai Reader — извлечение полного текста по URL (rate limits не указаны на странице).

### Примечания по автоматизации
- Часть RSS‑фидов возвращают 400 в инструментах без user‑agent; нужен проверочный fetch в окружении.
- Для HTML‑страниц без RSS использовать скрапинг + r.jina.ai для full‑text.

## [ТЕМА: Локальная LLM и API endpoints для AI-анализатора]
_Последнее обновление: 2026-03-14 | Роль: AI & Local LLM Engineer_
Актуально

### Подтвержденные API endpoints
- OpenAI Responses API: https://api.openai.com/v1/responses (официальный API reference).
- OpenAI Chat Completions: https://api.openai.com/v1/chat/completions (migration guide подтверждает endpoint).
- Mistral Chat Completions: https://api.mistral.ai/v1/chat/completions (официальный docs пример).
- DeepSeek OpenAI‑compatible base URL: https://api.deepseek.com (документация указывает base_url).
- Ollama Local API Chat: POST http://localhost:11434/api/chat (официальный Ollama API).

### Локальные модели (open‑source)
- Qwen2.5‑7B‑Instruct: контекст 131,072; лицензия Apache‑2.0. Рекомендована как базовая бесплатная модель для 24/7 локального инференса.
- Llama‑3.1‑8B‑Instruct: контекст 131,072; альтернатива при доступности.

### Примечания
- Для Ollama подтверждено имя модели в библиотеке: qwen2.5:7b-instruct.

## [ТЕМА: Бесплатные модели и free tiers — Groq, OpenRouter, прочие провайдеры]
_Последнее обновление: 2026-03-14 | Роль: AI & Local LLM Engineer_
Актуально

### OpenRouter (официальные источники)
- Pricing + rate limits: https://openrouter.ai/pricing и https://openrouter.ai/docs/limits
- Free Models Router: https://openrouter.ai/models/openrouter/free и https://openrouter.ai/docs/api-reference/overview
- Коллекции free‑моделей: https://openrouter.ai/collections/free-models

### OpenRouter (примеры free‑моделей из официальных карточек)
- https://openrouter.ai/models/openai/gpt-oss-120b:free
- https://openrouter.ai/models/qwen/qwen3-4b:free
- https://openrouter.ai/models/nvidia/nemotron-3-super-120b-a12b:free
- https://openrouter.ai/models/arcee-ai/trinity-large-preview:free

### Groq (официальные источники/сообщество)
- Docs: Rate limits — https://console.groq.com/docs/rate-limits
- Модели: https://console.groq.com/docs/models (список также доступен через GET https://api.groq.com/openai/v1/models с ключом)
- Free tier и лимиты по моделям в Groq Console → Limits (подтверждается в https://groq.com/groqcloud/) и в Groq Community.
- Внешний список model IDs с указанием production/preview: https://ai.pydantic.dev/models/groq/

### Прочие бесплатные/почти бесплатные варианты
- Cloudflare Workers AI: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Hugging Face Inference Providers: https://huggingface.co/pricing
- Fireworks AI: https://fireworks.ai/pricing
- Together AI: https://www.together.ai/pricing

## [ТЕМА: Cloudflare Workers (free 24/7) для Telegram бота]
_Последнее обновление: 2026-03-14 | Роль: Архитектор и инженер ботов_
Актуально

### Workers Free Limits
- Requests: 100,000/день; CPU time 10 ms; Memory 128 MB; Subrequests 50/req. (Workers Free). Источник: Cloudflare Workers Limits.

### D1 Free Limits
- Rows read: 5,000,000/день; Rows written: 100,000/день; Storage: 5 GB (Free plan). Источник: Cloudflare Workers pricing/D1 pricing.
- Доп. лимиты D1: 10 DBs на Free, max DB size 500 MB, max storage 5 GB. Источник: D1 Limits.

### Языки
- Workers поддерживает JS/TS, Rust, Python Workers (Python on Workers). Источник: Cloudflare Workers Languages / Python Workers.

### Обновление 2026-03-14 (web.run)
- Groq Rate Limits: официальная таблица с model IDs и лимитами RPM/RPD/TPM/TPD опубликована в GroqDocs (console.groq.com/docs/rate-limits).
- OpenRouter limits: для free-моделей (:free) лимит 20 req/min и 50 req/day без покупок; при >=10 credits — 1000 req/day (openrouter.ai/docs/api-reference/limits и FAQ).
- OpenRouter Free Models Router: openrouter/free — бесплатный роутер с /M tokens и 200k context (openrouter.ai/openrouter/free).
- Коллекция free-моделей OpenRouter: открытый список и ранжирование (openrouter.ai/collections/free-models).
- grammY Cloudflare Workers (Node.js) guide подтверждает использование webhookCallback в Workers (grammy.dev/hosting/cloudflare-workers-nodejs).


## [ТЕМА: Обновление лимитов Workers/D1 и агрегаторы RSS]
_Последнее обновление: 2026-03-15 | Роль: DevOps инженер и специалист по CI/CD_
Актуально

### Подтвержденные факты и ссылки
- Workers Free лимиты: 100,000 запросов/день и ограничения на subrequests и wall time (официальные Limits).
  Источник: https://developers.cloudflare.com/workers/platform/limits/
- D1 free-tier: при превышении дневных лимитов запросы блокируются до ежедневного ресета (release notes).
  Источник: https://developers.cloudflare.com/d1/platform/release-notes/
- Anthropic API release notes: официальный changelog на платформе Claude.
  Источник: https://platform.claude.com/docs/en/release-notes/overview
- Агрегированный RSS-канал AI источников (Planet AI) как дополнительный источник.
  Источник: https://planet-ai.net/ai-rss-feed.html (RSS: https://planet-ai.net/rss.xml)

## [ТЕМА: RSS/Atom источники для AI-новостей — доп. проверка]
_Последнее обновление: 2026-03-15 | Роль: DevOps инженер и специалист по CI/CD_
Актуально (часть источников подтверждена официальными страницами)

### Подтвержденные источники/каталоги
- NVIDIA официальный RSS каталог (Blog/Developer Blog): https://www.nvidia.com/en-us/about-nvidia/rss/
- MIT News RSS + темы (в т.ч. Artificial Intelligence): https://news.mit.edu/rss
- OpenAI News RSS (community reference): https://community.openai.com/t/rss-feed-openai-research-index-rss-feed/1088852
- Planet AI агрегатор (30+ AI-источников): https://planet-ai.net/ai-rss-feed.html (RSS: https://planet-ai.net/rss.xml)
- Hugging Face Blog RSS: https://huggingface.co/blog/feed.xml (упоминается в HF forum issue)
- Hacker News API (официальное объявление Firebase): https://firebase.googleblog.com/2014/10/hacker-news-now-has-api-its-firebase.html
- Google Blog RSS (официальный RSS feed link на странице AI раздела): https://blog.google/technology/ai/ (RSS: https://blog.google/rss/)
- Microsoft Research Blog RSS (официальная ссылка Subscribe to RSS): https://www.microsoft.com/en-us/research/feed/

### Нужна дополнительная верификация (кандидаты на добавление)
- DeepMind Blog RSS / Google AI Blog / Meta AI Blog / Microsoft AI Blog — требуется подтвердить официальные RSS/Atom URL.

## [ТЕМА: Telegram боты‑агрегаторы — меню/действия]
_Последнее обновление: 2026-03-15 | Роль: DevOps инженер и специалист по CI/CD_
Актуально

### Наблюдаемые паттерны у похожих ботов
- RSS‑боты: подписка на источники и авто‑доставка новых публикаций в Telegram; упор на автоматическую рассылку и фильтры. Источник: Feed Reader Bot. 
- Автопостинг в Telegram из RSS: упор на авто‑доставку каждого нового элемента и фильтрацию по ключевым словам. Источник: RSS.app.
- Дайджест‑боты: создание запланированных дайджестов по расписанию и генерация кратких сводок. Источник: Junction Bot.

### Официальные меню/команды Telegram
- Bot API поддерживает командное меню (setMyCommands/getMyCommands) и настраиваемую кнопку меню (setChatMenuButton). Источник: core.telegram.org Bot API.
- Меню‑кнопка может открывать список команд или Mini App; поведение задаётся через setBotMenuButton (MTProto) / setChatMenuButton (Bot API). Источник: core.telegram.org Bot menu button.

## [ТЕМА: Расширение RSS/JSON источников для AI‑дайджеста]
_Последнее обновление: 2026-03-15 | Роль: DevOps инженер и специалист по CI/CD_
Актуально

### Проверенные источники/URL
- TechCrunch RSS: https://techcrunch.com/feed/ (страница TechCrunch Subscribing).
- VentureBeat main feed (FeedBurner): https://feeds.feedburner.com/VentureBeat (страница venturebeat-rss).
- Ars Technica AI feed: https://arstechnica.com/ai/feed/ (greenlinks list).
- IEEE Spectrum AI feed: https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss (greenlinks list).
- MIT Technology Review feed: https://www.technologyreview.com/feed (feedsin.space list).
- The Verge RSS (general, фильтрация по ключам): https://www.theverge.com/rss/index.xml (greenlinks list).
- AI Scoop feed: https://aiscoop.com/feed/ (greenlinks list).
- Hugging Face Daily Papers RSS: https://papers.takara.ai/api/feed (Hugging Face пост).
- Reddit JSON endpoints (top/new): https://www.reddit.com/r/{subreddit}/top/.json + raw_json=1 (Beam example).
- Wired AI feed: https://www.wired.com/feed/tag/ai/latest/rss (Wired RSS page).

## [ТЕМА: Cloudflare Workers AI — binding + модель 8B]
_Последнее обновление: 2026-03-15 | Роль: DevOps инженер и специалист по CI/CD_
Актуально

### Подтвержденные факты
- Workers AI binding задаётся в wrangler.toml через секцию [ai] и имя binding.
- Модель 8B в каталоге Workers AI: @cf/meta/llama-3.1-8b-instruct.

## [ТЕМА: Метрики Telegram-каналов и психология новостного потребления]
_Последнее обновление: 2026-03-16 | Роль: DevOps инженер и специалист по CI/CD_
Актуально (обновлено web-исследованием)

### Проверенные источники (использовано в синтезе)
- Postmypost (08.04.2025): влияние частоты публикаций на просмотры в Telegram.
  https://postmypost.io/resources/research-how-posting-frequency-affects-the-number-of-post-views-on-telegram/
- Postmypost (15.04.2025): лучшее время публикации в Telegram и поведенческие особенности.
  https://postmypost.io/resources/the-best-time-to-post-on-telegram-in-2025/

### Ключевые выводы для продукта
- 1 пост/день дает максимальный охват; 2 поста дают ~20% снижения между первым и вторым; 3 поста допустимы, но в крупных каналах третья публикация теряет до 25–30% просмотров; 4+ поста дают резкое падение. Исключение: news‑каналы могут публиковать чаще. Источник: Postmypost 08.04.2025.
- В Telegram лента хронологическая, публикации конкурируют по времени выхода, а уведомления часто отключены; поэтому тайминг и «первые строки» критичны. Источник: Postmypost 15.04.2025.
- Окна активности для постинга в 2025: 13:00–16:00 и 18:00–22:00; лучшие дни — будни, худшие — выходные. Источник: Postmypost 15.04.2025.

### Что нужно перепроверить при следующем обновлении
- Актуальные ER/Views/CTR метрики Telegram-каналов на март 2026 (TGStat/Telemetr/Combot/официальные источники).
- Психология заголовков и чтения в мессенджерах (academia + industry reports).
- Best practices по частоте/объему для новостных каналов в Telegram.
