# WORLD-CLASS PRODUCT UPGRADE REPORT: SearchAInews

## EXECUTIVE SUMMARY FOR HUMANS

- SearchAInews уже умеет делать важную вещь: собирать AI-новости, отсеивать шум и превращать их в короткие практические выводы. Проблема в том, что эта сила пока лучше видна в канале, чем в личном боте. Первый шаг: выровнять личную выдачу под тот же компактный и понятный стандарт.
- Сейчас продукт больше похож на “умный internal engine с Telegram-обёрткой”, чем на world-class user product. Это мешает росту, потому что пользователь не получает архив, поиск, объяснение релевантности и удобный способ возвращаться к ценным находкам. Первый шаг: добавить историю, поиск и “почему вы это получили”.
- Главное продуктовое обещание звучит как “релевантные AI-апдейты по роли”, но локальные данные уже показывают дрейф ролей. Это подтачивает доверие. Первый шаг: очистить role taxonomy и привести pipeline, corpus и bot delivery к одному словарю.
- У бота нет сильного Telegram-native growth surface. Он живой, но не использует inline mode, deep-link attribution и share loops. Первый шаг: сделать inline mode для быстрого шаринга и поиска новостей прямо в любых чатах.
- Канальный editorial pattern уже выглядит сильнее, чем личный digest. Это хорошо: есть что сохранить и масштабировать. Первый шаг: перенести channel discipline в user digest, а не переписывать всё заново.
- Платформа уже живая, но операционно хрупкая. Это не только release-проблема: отсутствие нормального curation/replay/operator surface замедляет улучшения самого продукта. Первый шаг: сделать операторскую очередь для review, replay и ручной коррекции выдачи.
- World-class bar здесь достигается не “ещё 50 источниками”, а пятью вещами: меньше шума, лучше relevance, быстрее time-to-value, выше trust, сильнее retention loop. Первый шаг: строить roadmap вокруг этих пяти измерений, а не вокруг количества фич.

## IF EXPLAINED SIMPLY

Если простым языком: продукт уже хорошо задуман, но сейчас ему больше всего мешают не идеи, а разрывы между “умной начинкой” и тем, как человек реально получает пользу.

- Нужно сделать личную выдачу короче и жёстче по структуре -> сейчас одно сообщение перегружает пользователя -> это даст ощущение, что бот быстро помогает, а не заставляет читать стену текста.
- Нужно объяснять, почему эта новость показана именно этому человеку -> сейчас персонализация выглядит частично “на веру” -> это повысит доверие к боту.
- Нужно починить роли один раз и везде -> сейчас система местами думает в одних ролях, а показывает другие -> это уберёт ощущение случайной релевантности.
- Нужно дать историю и поиск -> сейчас полезная новость исчезает в потоке -> пользователь сможет возвращаться к уже найденному, а не начинать заново.
- Нужно сделать удобный способ делиться находками в Telegram -> сейчас бот полезен, но плохо растёт внутри самого Telegram -> это даст органическое распространение.
- Нужно группировать одну и ту же историю из разных источников -> сейчас продукт может показывать несколько версий одного события -> это уменьшит шум и усилит ощущение редакторского качества.
- Нужно показывать, насколько источник заслуживает доверия -> сейчас пользователь видит вывод, но не всегда видит силу источника -> это помогает быстрее решать, чему верить.
- Нужно дать простые настройки частоты и глубины -> сейчас есть почти только “подписка включена/выключена” -> это сделает бот удобнее для разных типов людей.
- Нужно добавить обратную связь “это полезно / не полезно / больше такого” -> сейчас продукт почти не учится от поведения пользователя -> это даст основу для реального улучшения relevance.
- Нужно сделать операторский пульт хотя бы в минимальном виде -> сейчас редактору сложнее быстро исправлять и усиливать выдачу -> это ускорит развитие продукта без больших переписываний.
- Нужно измерять, что происходит после первого использования -> сейчас трудно понять, возвращаются ли люди и почему уходят -> это поможет строить продукт на фактах, а не на ощущениях.
- Нужно привести документацию, runtime и product promise к одной правде -> сейчас часть правды живёт в коде, часть в отчётах, часть в голове -> это снизит хаос и ускорит следующие улучшения.

## AI / OPERATOR SNAPSHOT

- `VERIFIED_LOCAL` Surface: `HYBRID` = Python ingestion + local SQLite corpus + Cloudflare Worker bot/runtime + Telegram channel.
- `VERIFIED_LOCAL` Core truth files: `config.yaml` для источников, `cf_worker/wrangler.toml` для runtime, `cf_worker/schema.sql` для D1 schema, `cf_worker/src/*` для bot/channel behavior.
- `VERIFIED_LIVE` Live runtime: `@impactpulse_bot`, webhook на Worker, `GET /health = ok`, latest scheduled GitHub Actions ingest run `25066623478 = success`.
- `VERIFIED_LOCAL` Corpus scale в локальной БД на дату анализа: `587` items, `333` with `full_text`, `54` scored, `40` with `impact_score >= 3`.
- `VERIFIED_LOCAL` Role drift подтверждён в scored corpus: помимо current UI-ролей есть `ml_engineer`, `developer`, `ops`, `other`.
- `VERIFIED_LOCAL` Personal menu и digest живут как text-first Telegram UX без archive/search/history surface.
- `VERIFIED_LIVE` Bot growth surfaces слабы: `supports_inline_queries=false`, `has_main_web_app=false`, menu button = `commands`.
- `BLOCKED` Нет доказанного current user retention/DAU/conversion, потому что KPI layer почти отсутствует.

## VERIFIED LOCAL REALITY

- `VERIFIED_LOCAL` Проект уже не заготовка: есть end-to-end pipeline `scraper -> ai_analyzer -> push_to_worker -> Worker delivery`.
- `VERIFIED_LOCAL` Самая сильная authored product logic находится не в legacy `bot/`, а в `cf_worker/src/services/channel.ts`, `broadcast.ts`, `news.ts` и `users.ts`.
- `VERIFIED_LOCAL` Главное меню бота даёт только 7 базовых действий: `10 новостей`, `20 новостей`, `Настройки`, `Роль`, `Язык`, `О боте`, `Помощь`.
- `VERIFIED_LOCAL` Personalization сейчас ограничена тремя простыми осями: роль, язык, подписка.
- `VERIFIED_LOCAL` В bot UX нет history/search/save/share/favorite/report-feedback surfaces.
- `VERIFIED_LOCAL` `getLatestForRole()` уже делает age filter, dedupe по доменам и темам и fallback, но всё ещё зависит от неполно чистой role taxonomy.
- `VERIFIED_LOCAL` Channel logic уже использует более зрелый editorial pattern: краткий summary, `Что проверить`, source quality bias, dedupe keys.
- `VERIFIED_LOCAL` Operator tooling есть, но фрагментарно: `diagnose_bot.py`, `validate_*`, `source_health_report.py`, webhook helpers, без единого curation console.
- `VERIFIED_LOCAL` Release/docs truth до сегодняшнего прохода дрейфовала; во время анализа были выровнены `README.md`, `API.md`, `.env.example`, `DEPLOY_CLOUDFLARE.md`.

## VERIFIED LIVE REALITY

- `VERIFIED_LIVE` `@impactpulse_bot` жив и отвечает через production webhook path `.../webhook/<secret>`.
- `VERIFIED_LIVE` `py scripts/diagnose_bot.py` на `2026-04-28` дал `getMe ok`, `pending_update_count=0`, `worker /health=200`, `debug webhook status=200`.
- `VERIFIED_LIVE` Последний scheduled ingest pipeline на GitHub завершился `success`.
- `VERIFIED_LIVE` `py scripts/send_test_message.py` дал `sendMessage status: 200`, то есть outbound Telegram delivery работает.
- `VERIFIED_LIVE` Визуально onboarding уже понятен: первый экран объясняет продукт и ведёт к выбору языка.
- `VERIFIED_LIVE` Визуально channel-post читается лучше, чем personal digest: headline, summary и next step разделены яснее.
- `VERIFIED_LIVE` Визуально главное меню перегружено равновесными CTA, а personal digest слишком длинный для мобильного чтения.
- `BLOCKED` Не был получен нативный live transcript полного диалога `/start -> role -> latest` из Telegram chat history; есть только runtime probes, screenshots и code-backed preview.

## VERIFIED EXTERNAL BENCHMARKS

- `VERIFIED_EXTERNAL` [Feedly AI / Leo](https://feedly.com/ai): сильный паттерн не в “AI summary”, а в user-controlled signal shaping. Забрать: boards, alerts, mute/prioritize, follow-by-topic/company, чтобы пользователь сам настраивал шум и важность.
- `VERIFIED_EXTERNAL` [Particle](https://particle.news/): сильный паттерн story-level grouping и “несколько точек зрения на одно событие”. Забрать: объединение дублей вокруг одной истории и объяснение контекста, а не просто список ссылок.
- `VERIFIED_EXTERNAL` [Techmeme](https://www.techmeme.com/about): сильный паттерн editorial clustering и source hierarchy. Забрать: основной источник + supporting links + conversation context, чтобы одна тема не дублировалась пять раз.
- `VERIFIED_EXTERNAL` [Superhuman AI](https://www.superhuman.ai/): сильный паттерн предсказуемого короткого формата и чёткого promise “быстро понять главное”. Забрать: жёсткий skim format и постоянный reading contract.
- `VERIFIED_EXTERNAL` [Ben's Bites](https://www.bensbites.com/): сильный паттерн community-first packaging и archive visibility. Забрать: понятный public archive и ощущение “я могу быстро вернуться к прошлым находкам”.
- `VERIFIED_EXTERNAL` [The Rundown AI](https://www.therundown.ai/): сильный паттерн growth packaging вокруг одной ежедневной привычки. Забрать: один очень понятный recurring ritual, а не просто общий новостной бот.
- `VERIFIED_EXTERNAL` [TLDR AI](https://tldr.tech/ai): сильный паттерн сверхкраткого, стабильного, сканируемого digest формата. Забрать: жёсткий лимит длины и predictable information density.
- `VERIFIED_EXTERNAL` [Perplexity Discover / Collections](https://www.perplexity.ai/discover): сильный паттерн topic-following и collection-based exploration. Забрать: “подпишись на тему/компанию/тип сигнала”, а не только на общую рассылку.
- `VERIFIED_EXTERNAL` [Telegram Bot Features](https://core.telegram.org/bots/features): для content/search bot релевантны inline mode, deep linking и rich sharing. Забрать: рост через Telegram-native entry points, а не только через `/start`.

## GITHUB / OSS LEVERAGE

- `VERIFIED_EXTERNAL` [miniflux/v2](https://github.com/miniflux/v2) — `READY TO REUSE` как паттерн archive/read-status/search discipline. Забрать: read/unread, save, archive semantics, а не полный UI.
- `VERIFIED_EXTERNAL` [RSSHub/RSSHub](https://github.com/RSSHub/RSSHub) — `ADAPTABLE` для source coverage и feed resiliency. Забрать: route-based adapters и часть broken-site handling, чтобы меньше зависеть от ad hoc scraping.
- `VERIFIED_EXTERNAL` [grammY](https://github.com/grammyjs/grammY) — `READY TO REUSE` для inline mode/conversation patterns; живая issue/activity база подтверждает актуальность. Забрать: official framework path для inline queries и testing harnesses.
- `VERIFIED_EXTERNAL` [PostHog/posthog](https://github.com/PostHog/posthog) — `ADAPTABLE` для event/funnel/retention instrumentation. Забрать: event schema и retention/funnel thinking, не обязательно весь стек.
- `VERIFIED_EXTERNAL` [umami-software/umami](https://github.com/umami-software/umami) — `ADAPTABLE` как более лёгкий analytics path. Забрать: минимальную privacy-friendly event telemetry, если PostHog кажется тяжёлым.
- `VERIFIED_EXTERNAL` [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) — `INSPIRATION ONLY` для archive search и instant retrieval. Забрать: fast search contract и ranking ideas, но не тащить тяжёлую зависимость преждевременно.
- `VERIFIED_EXTERNAL` [typesense/typesense](https://github.com/typesense/typesense) — `INSPIRATION ONLY` для typo-tolerant search и filtering. Забрать: search UX principles.
- `VERIFIED_EXTERNAL` [metarank/metarank](https://github.com/metarank/metarank) — `ADAPTABLE` позже для personalized ranking. Забрать: ranking signals model, а не отдельный сервис на первом шаге.

## PRESERVED STRENGTHS

- `VERIFIED_LOCAL` Multi-source ingestion и enrichment уже дают хороший raw-material base.
- `VERIFIED_LIVE` Канальный формат уже ближе к product-grade readability, чем личный digest.
- `VERIFIED_LOCAL` Бот остаётся text-first и не перегружен лишней декоративностью.
- `VERIFIED_LOCAL` Bilingual surface уже существует; это нельзя потерять при перепаковке.
- `VERIFIED_LOCAL` У продукта есть developer-first editorial angle, который отличает его от просто “ещё одной AI-рассылки”.
- `VERIFIED_LIVE` Runtime уже живой; улучшения надо строить поверх работающего ядра, а не через тотальный снос.

## KEY PROBLEMS IN PLAIN LANGUAGE

- `VERIFIED_LOCAL` Продукт обещает персональную релевантность, но внутри ещё не до конца договорился сам с собой, какие роли он обслуживает. Пользователь может получать “умную” выдачу, но ощущение точности пока не железное.
- `VERIFIED_LIVE` Личная выдача слишком длинная. Пользователь открывает бота не ради чтения большой карточки, а ради быстрого ответа на вопрос “что важно и что мне делать”.
- `VERIFIED_LOCAL` Полезные новости пропадают в потоке. Если человек не сохранил сообщение сразу, потом вернуться к нему почти некуда.
- `VERIFIED_LIVE` Бот пока плохо растёт внутри Telegram. Нет удобного механизма кинуть новость в другой чат, вызвать бота inline или зайти через умный deep link.
- `VERIFIED_LOCAL` Система не учится от поведения пользователя. Она умеет оценивать новости, но почти не умеет понимать, что человеку реально оказалось полезно.
- `VERIFIED_LOCAL` Оператору не хватает “редакторского руля”. Это замедляет повышение качества сильнее, чем кажется.
- `VERIFIED_LOCAL` Доверие к продукту страдает не из-за одной большой ошибки, а из-за мелких рассинхронов: роли, docs, release path, отсутствие явной source confidence.

## PRIORITY ORDER

### DO FIRST
- Убрать role drift и связать pipeline, corpus и delivery в один product contract.
- Переписать personal digest под короткий, жёсткий, scan-first формат.
- Добавить историю, поиск и сохранение полезных items.
- Включить inline mode как основной Telegram-native growth surface.

### DO NEXT
- Ввести story clustering и canonical source selection.
- Добавить feedback loop и “почему вы получили это”.
- Дать пользователю настройки frequency/depth/source classes.
- Сделать operator curation/replay queue.

### DO LATER
- Усилить analytics/retention instrumentation.
- Добавить topic follows, company follows и saved collections.
- Построить smarter ranking с behavioural signals.
- Расширить archive/search до knowledge workspace.

### NOT NOW
- Mini App.
- Монетизация.
- Геймификация.
- Большой визуальный ребрендинг.

## GAP MAP BY DIMENSION

| Dimension | State | Gap |
|---|---|---|
| Value clarity | Сильная идея, но promise частично разъезжается с roles | Нужен единый role/product contract |
| Onboarding | Понятный first step | Не хватает follow-up activation и expectation setting |
| Speed to outcome | Средний | Digest длинный, next step не всегда мгновенно понятен |
| Usefulness depth | Средняя | Нет history/search/save/feedback |
| Workflow fit | Средний | Хорошо для “посмотреть сейчас”, слабо для “вернуться позже” |
| Trust | Средний | Не хватает source trust metadata и ясности relevance |
| Resilience | Средняя | Runtime жив, но release/ops path хрупкий |
| Supportability | Средняя | Есть scripts и alerts, нет operator console |
| Collaboration/sharing | Слабая | Нет inline/share/deep-link loops |
| Accessibility/clarity | Средняя | Канал лучше digest, меню перегружено |
| Performance | Средняя | Baseline хорош, tail latency под burst расползается |
| Extensibility | Средняя | Есть ядро, но много drift между legacy/current truth |
| Retention | Слабая | Нет measured loops, history, saved collections, feedback |

## UPGRADE BACKLOG 20+

1. **U01 — Unify Role Contract**
   - Type: `High Leverage`
   - Surface / Dimension: Personalization / Trust
   - Current Gap: corpus и delivery используют несовпадающие роли
   - Evidence: `VERIFIED_LOCAL` local DB roles + `role.ts` + `news.ts`
   - Benchmark / Reference: Feedly topic model; Particle follow model
   - Concrete Change: ввести один canonical role dictionary, migration legacy roles, analyzer prompt alignment
   - Why It Matters: без этого “релевантность” выглядит случайной
   - User-Visible Result: новости начнут точнее соответствовать роли
   - Expected Effect: выше trust, меньше false-positive delivery
   - Effort: `M`
   - Confidence: `High`
   - How To Validate: доля scored items с canonical roles = 100%, ручной relevance pass по 20 items

2. **U02 — Compress Personal Digest**
   - Type: `High Leverage`
   - Surface / Dimension: UX / Speed to outcome
   - Current Gap: личная карточка длиннее и тяжелее канальной
   - Evidence: `VERIFIED_LIVE` visual evidence
   - Benchmark / Reference: TLDR AI, Superhuman AI
   - Concrete Change: лимит 1 sentence summary + 1 sentence why + 1 action line + source
   - Why It Matters: бот должен сканироваться за секунды
   - User-Visible Result: один item читается без усталости
   - Expected Effect: выше open-to-value conversion
   - Effort: `S`
   - Confidence: `High`
   - How To Validate: screenshot diff + median message length drop

3. **U03 — Story Clustering**
   - Type: `High Leverage`
   - Surface / Dimension: Noise reduction / Editorial quality
   - Current Gap: одна история может прийти из 3-5 источников
   - Evidence: `VERIFIED_LOCAL` dossier + channel audit notes
   - Benchmark / Reference: Techmeme, Particle
   - Concrete Change: cluster by entity/title similarity, keep one canonical item plus supporting links
   - Why It Matters: world-class products remove duplicate thinking
   - User-Visible Result: меньше повторов, больше signal
   - Expected Effect: выше perceived quality
   - Effort: `M`
   - Confidence: `High`
   - How To Validate: duplicate-topic rate in sample batches

4. **U04 — Canonical Source Bias**
   - Type: `Quick Win`
   - Surface / Dimension: Trust
   - Current Gap: пользователь не всегда видит лучший источник первым
   - Evidence: `VERIFIED_LOCAL` channel logic already partly does this
   - Benchmark / Reference: Techmeme
   - Concrete Change: always prefer official/vendor/research source over aggregator if same story
   - Why It Matters: trust grows when best source wins
   - User-Visible Result: чище ссылки и меньше “reddit-first” impressions
   - Expected Effect: выше credibility
   - Effort: `S`
   - Confidence: `High`
   - How To Validate: sample editorial review of top 30 stories

5. **U05 — Add “Why You Got This”**
   - Type: `Quick Win`
   - Surface / Dimension: Trust / Explainability
   - Current Gap: relevance is implicit
   - Evidence: `VERIFIED_LOCAL` current digest format
   - Benchmark / Reference: Feedly follows/boards logic
   - Concrete Change: append short marker like “Для вашей роли: AI Developer, потому что API/tooling impact”
   - Why It Matters: people trust relevance more when it is explained
   - User-Visible Result: меньше ощущения случайной ленты
   - Expected Effect: выше trust and relevance perception
   - Effort: `S`
   - Confidence: `High`
   - How To Validate: user test on explanation clarity

6. **U06 — History / Recent Archive**
   - Type: `High Leverage`
   - Surface / Dimension: Utility depth / Retention
   - Current Gap: delivered value disappears into chat history
   - Evidence: `VERIFIED_LOCAL` no history surface
   - Benchmark / Reference: Miniflux archives, Ben's Bites archive
   - Concrete Change: add `/recent`, `/history`, last 7 days per user role
   - Why It Matters: useful products are revisit-able
   - User-Visible Result: можно вернуться к вчерашней новости
   - Expected Effect: higher repeat usage
   - Effort: `M`
   - Confidence: `High`
   - How To Validate: usage of `/recent`, revisit rate

7. **U07 — Search Across Corpus**
   - Type: `Strategic`
   - Surface / Dimension: Retrieval / Power use
   - Current Gap: no queryable memory
   - Evidence: `VERIFIED_LOCAL`
   - Benchmark / Reference: Miniflux, Meilisearch, Typesense
   - Concrete Change: add keyword search over D1/local corpus with source/date filters
   - Why It Matters: turns bot from feed into tool
   - User-Visible Result: “найди все новости про GLM-5”
   - Expected Effect: deeper utility and lower churn
   - Effort: `L`
   - Confidence: `Medium`
   - How To Validate: search success on 10 canned queries

8. **U08 — Save / Favorite Items**
   - Type: `High Leverage`
   - Surface / Dimension: Retention / Personal knowledge
   - Current Gap: no lightweight bookmarking
   - Evidence: `VERIFIED_LOCAL`
   - Benchmark / Reference: Miniflux starred/bookmarked semantics
   - Concrete Change: add `Save` button and `/saved`
   - Why It Matters: saves useful items from chat entropy
   - User-Visible Result: личная мини-библиотека инсайтов
   - Expected Effect: stronger habit loop
   - Effort: `M`
   - Confidence: `High`
   - How To Validate: saved items count and return visits

9. **U09 — Inline Mode**
   - Type: `High Leverage`
   - Surface / Dimension: Growth / Telegram-native
   - Current Gap: `supports_inline_queries=false`
   - Evidence: `VERIFIED_LIVE`
   - Benchmark / Reference: Telegram inline docs, grammY
   - Concrete Change: implement inline search for latest stories, topics, saved brief cards
   - Why It Matters: gives the bot a native distribution loop inside Telegram
   - User-Visible Result: пользователь может искать и делиться новостями прямо в других чатах
   - Expected Effect: higher discovery and virality
   - Effort: `L`
   - Confidence: `High`
   - How To Validate: inline query count, share-to-open ratio

10. **U10 — Deep Link Attribution**
    - Type: `Quick Win`
    - Surface / Dimension: Growth / Analytics
    - Current Gap: no deep-link payload parsing
    - Evidence: `VERIFIED_LOCAL` BOT-006
    - Benchmark / Reference: Telegram deep linking
    - Concrete Change: parse `start=...` for source attribution, campaigns, referrals, role presets
    - Why It Matters: growth without attribution is guesswork
    - User-Visible Result: smarter landing flows
    - Expected Effect: better onboarding conversion measurement
    - Effort: `S`
    - Confidence: `High`
    - How To Validate: start payload captured in events

11. **U11 — Feedback Buttons**
    - Type: `High Leverage`
    - Surface / Dimension: Relevance learning
    - Current Gap: system does not learn from usefulness
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: modern recommendation products, PostHog event model
    - Concrete Change: add `Useful`, `Not useful`, `More like this`, `Less from this source`
    - Why It Matters: feedback is the shortest route to better ranking
    - User-Visible Result: бот начинает “понимать вкус”
    - Expected Effect: better retention and relevance
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: feedback event volume + relevance delta

12. **U12 — User Controls for Frequency and Depth**
    - Type: `High Leverage`
    - Surface / Dimension: Personalization
    - Current Gap: only subscribe/unsubscribe
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: Feedly alerts, newsletter preference centers
    - Concrete Change: `manual only / hourly / daily`, `compact / standard`
    - Why It Matters: one cadence does not fit all
    - User-Visible Result: fewer annoying digests, more chosen digests
    - Expected Effect: lower unsubscribe rate
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: preference adoption and unsubscribe trend

13. **U13 — Topic / Source Class Follows**
    - Type: `Strategic`
    - Surface / Dimension: Personalization depth
    - Current Gap: role alone is too coarse
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: Feedly follows, Perplexity collections
    - Concrete Change: allow opt-ins like `OpenAI`, `agents`, `research`, `official`, `community`
    - Why It Matters: people care about slices, not just roles
    - User-Visible Result: much tighter feed
    - Expected Effect: improved engagement
    - Effort: `L`
    - Confidence: `Medium`
    - How To Validate: follow usage + open rates by topic

14. **U14 — Source Trust Metadata**
    - Type: `Quick Win`
    - Surface / Dimension: Trust / Clarity
    - Current Gap: source strength is implicit
    - Evidence: `VERIFIED_LIVE` channel preview already hints at bias
    - Benchmark / Reference: Techmeme, Particle
    - Concrete Change: show `Official`, `Research`, `Media`, `Community` badges
    - Why It Matters: fast trust assessment
    - User-Visible Result: user instantly knows how “hard” the evidence is
    - Expected Effect: higher confidence in actions
    - Effort: `S`
    - Confidence: `High`
    - How To Validate: comprehension test on screenshots

15. **U15 — Operator Curation Queue**
    - Type: `Strategic`
    - Surface / Dimension: Operability / Quality control
    - Current Gap: no simple review/replay surface for scored items
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: editorial queues, internal moderation tools
    - Concrete Change: build minimal operator list for pending/high-impact/rejected/replay items
    - Why It Matters: biggest quality improvements often need 30 seconds of human steering
    - User-Visible Result: better posts and fewer awkward items
    - Expected Effect: faster product quality climb
    - Effort: `L`
    - Confidence: `High`
    - How To Validate: operator time to fix or resend item

16. **U16 — Replay / Resend Controls**
    - Type: `Quick Win`
    - Surface / Dimension: Operability
    - Current Gap: recovery is script-heavy
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: broadcast consoles
    - Concrete Change: add resend last digest / replay channel candidate / mark as skipped
    - Why It Matters: fixes become operationally cheap
    - User-Visible Result: fewer silent misses
    - Expected Effect: stronger supportability
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: mean time to recover missed item

17. **U17 — Event Telemetry Baseline**
    - Type: `High Leverage`
    - Surface / Dimension: Analytics / Product learning
    - Current Gap: no real KPI layer
    - Evidence: `VERIFIED_LOCAL` BOT-007
    - Benchmark / Reference: PostHog, Umami
    - Concrete Change: instrument start, role picked, latest clicked, item opened, saved, feedback, subscribe, unsubscribe
    - Why It Matters: no world-class upgrade without measured behavior
    - User-Visible Result: indirect but critical; product improves faster
    - Expected Effect: evidence-based roadmap
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: event dashboard exists and is populated

18. **U18 — Activation Funnel Dashboard**
    - Type: `High Leverage`
    - Surface / Dimension: Growth / Product analytics
    - Current Gap: no visibility into where users drop
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: PostHog funnels
    - Concrete Change: funnel = `start -> language -> role -> latest -> subscribe`
    - Why It Matters: reveals the highest-ROI UX fixes
    - User-Visible Result: better onboarding over time
    - Expected Effect: higher activation
    - Effort: `S`
    - Confidence: `High`
    - How To Validate: weekly funnel trend

19. **U19 — Rewrite Menu Hierarchy**
    - Type: `Quick Win`
    - Surface / Dimension: Navigation
    - Current Gap: primary and secondary actions have same weight
    - Evidence: `VERIFIED_LIVE` screenshot
    - Benchmark / Reference: better CTA grouping in lightweight bots
    - Concrete Change: first row = `Get digest`, second row = `Tune me`, third row = `Help/About`
    - Why It Matters: users should not think about navigation
    - User-Visible Result: faster first useful action
    - Expected Effect: less friction
    - Effort: `S`
    - Confidence: `High`
    - How To Validate: menu click distribution

20. **U20 — Channel-to-Bot Continuity**
    - Type: `High Leverage`
    - Surface / Dimension: Cross-surface consistency
    - Current Gap: channel feels more polished than bot
    - Evidence: `VERIFIED_LIVE`
    - Benchmark / Reference: The Rundown/Superhuman consistent skim format
    - Concrete Change: use same summary contract and action-line discipline across bot and channel
    - Why It Matters: one product should feel like one product
    - User-Visible Result: stronger product identity
    - Expected Effect: improved perceived quality
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: side-by-side template audit

21. **U21 — Archive Landing Surface**
    - Type: `Strategic`
    - Surface / Dimension: Support / Self-serve
    - Current Gap: no public archive or web mirror
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: Ben's Bites archive, TLDR archive
    - Concrete Change: simple web archive or channel-linked digest archive page
    - Why It Matters: expands trust and discoverability beyond chat
    - User-Visible Result: easier sharing and backreading
    - Expected Effect: organic SEO/social utility
    - Effort: `L`
    - Confidence: `Medium`
    - How To Validate: archive visits and shared links

22. **U22 — Searchable Operator Incident Notes**
    - Type: `Quick Win`
    - Surface / Dimension: Operability / Reliability
    - Current Gap: operational truth is scattered across docs and memory
    - Evidence: `VERIFIED_LOCAL`
    - Benchmark / Reference: simple runbooks
    - Concrete Change: centralize incident/runbook notes in one operator doc with last-known-good actions
    - Why It Matters: faster recovery, less repeated confusion
    - User-Visible Result: indirect but fewer outages and regressions
    - Expected Effect: lower ops friction
    - Effort: `S`
    - Confidence: `High`
    - How To Validate: re-run issue from runbook without ad hoc digging

23. **U23 — Burst-Path Performance Hardening**
    - Type: `Strategic`
    - Surface / Dimension: Performance / Reliability
    - Current Gap: tail latency degrades under modest burst
    - Evidence: `VERIFIED_LOCAL` prior perf report
    - Benchmark / Reference: graceful queueing and jitter best practices
    - Concrete Change: improve rate-limit strategy, jittered retries, lighter webhook path
    - Why It Matters: world-class products stay crisp under spikes
    - User-Visible Result: fewer slowdowns during bursts
    - Expected Effect: better p95/p99
    - Effort: `M`
    - Confidence: `Medium`
    - How To Validate: repeat burst perf test

24. **U24 — Release and Runtime Truth Consolidation**
    - Type: `High Leverage`
    - Surface / Dimension: Operability / Trust
    - Current Gap: product truth split between legacy paths, docs and live worker
    - Evidence: `VERIFIED_LOCAL` unified/release audits
    - Benchmark / Reference: healthy product ops hygiene
    - Concrete Change: one current-truth runtime map, legacy marked explicitly, deployment ownership fixed
    - Why It Matters: product quality rises faster when the team knows what is real
    - User-Visible Result: fewer silent mismatches and regressions
    - Expected Effect: faster iteration
    - Effort: `M`
    - Confidence: `High`
    - How To Validate: next agent can deploy and reason without archaeology

## TOP 10 HIGHEST-LEVERAGE UPGRADES

- `U01 — Unify Role Contract`: убирает фундаментальную ложь в персонализации и даёт боту реальную relevance discipline.
- `U02 — Compress Personal Digest`: превращает тяжёлую карточку в быстрый, полезный answer surface.
- `U03 — Story Clustering`: резко уменьшает шум и делает продукт похожим на редактора, а не на scraper.
- `U06 — History / Recent Archive`: добавляет second-use value и снижает потерю полезных находок.
- `U09 — Inline Mode`: даёт сильный Telegram-native growth loop, которого сейчас нет.
- `U11 — Feedback Buttons`: создаёт short loop обучения продукта от реального поведения.
- `U12 — User Controls for Frequency and Depth`: уменьшает раздражение и повышает пригодность для разных типов пользователей.
- `U15 — Operator Curation Queue`: ускоряет рост качества без тяжёлой архитектурной революции.
- `U17 — Event Telemetry Baseline`: даёт факты вместо предположений о product progress.
- `U20 — Channel-to-Bot Continuity`: переносит уже существующую сильную редакторскую дисциплину в основную user surface.

Если простым языком, здесь главный смысл такой: не надо “добавить ещё много всего”; надо убрать ложную персонализацию, сократить шум, дать память и включить естественный рост внутри Telegram.

## QUICK WINS

- `U02 — Compress Personal Digest`: быстро даст ощущение более умного и дорогого продукта.
- `U04 — Canonical Source Bias`: укрепит доверие почти без большого рефакторинга.
- `U05 — Add “Why You Got This”`: сразу объяснит персонализацию человеческим языком.
- `U10 — Deep Link Attribution`: откроет ростовые и аналитические сценарии почти без тяжелой разработки.
- `U14 — Source Trust Metadata`: сделает сообщения заметно понятнее за малую цену.
- `U18 — Activation Funnel Dashboard`: даст числовую правду о том, где ломается onboarding.
- `U19 — Rewrite Menu Hierarchy`: уберёт лишнее трение на главном экране.
- `U22 — Searchable Operator Incident Notes`: снимет часть операционного хаоса.

Если простым языком, здесь главный смысл такой: уже за 1-2 короткие итерации можно сделать продукт заметно понятнее, честнее и полезнее, не переписывая его заново.

## STRATEGIC REBUILD OPPORTUNITIES

- `U03 + U04 + U14`: собрать story intelligence layer, где одна история имеет canonical source, confidence class и supporting links.
- `U06 + U07 + U08 + U21`: превратить бот из одноразовой ленты в searchable memory surface.
- `U09 + U10 + U13`: вырастить Telegram-native discovery and personalization engine.
- `U15 + U16 + U24`: построить operator-grade editorial control plane поверх уже живого ядра.

## NOT NOW

- `VERIFIED_LOCAL` Mini App: пока боту не хватает даже archive/search/inline surface; Mini App раньше времени только размоет фокус.
- `VERIFIED_LOCAL` Payments/Stars: сначала надо доказать retention и repeat value.
- `VERIFIED_LOCAL` Gamification: сейчас продукту нужнее trust и usefulness, а не игровые петли.
- `VERIFIED_LIVE` Большой визуальный ребрендинг: сначала надо укрепить content contract и navigation.

## DO NOT DO

- `INFERRED` Не расширяйте список источников как главную стратегию роста: это усилит шум быстрее, чем ценность.
- `INFERRED` Не делайте Mini App ради модности: без archive/search/value loops он будет красивой пустой оболочкой.
- `INFERRED` Не тащите тяжёлый search stack до появления доказанной потребности; сначала можно сделать D1-backed search surface.
- `VERIFIED_LOCAL` Не держите две продуктовые правды слишком долго: legacy/local bot и current worker должны быть разведены честно.
- `INFERRED` Не пытайтесь сразу строить “универсального AI-ассистента”: сила проекта сейчас именно в редакторской AI-news специализации.

## UNKNOWNS / BLOCKERS

- `BLOCKED` Нет текущих production retention/DAU/conversion метрик.
- `BLOCKED` Нет нативного live transcript полного пользовательского Telegram flow.
- `BLOCKED` Не подтверждён публичный channel URL и его реальная audience behavior.
- `BLOCKED` Нет свежего deep security audit для world-class trust layer.
- `BLOCKED` Release path всё ещё хрупкий из-за Cloudflare account mismatch и неготового deploy context.

## FINAL UPGRADE THESIS

SearchAInews не надо превращать в “большой медиа-портал” или “ещё один AI-чат”. Его world-class путь гораздо уже и сильнее: стать лучшим Telegram-native product для быстрого, доверяемого, role-aware AI signal intake. Для этого ему нужно не больше источников и не больше шума, а меньше трения, чище relevance, сильнее story intelligence, память о полезных находках и нормальный loop обучения от пользователя и оператора.

[P-WORLDCLASS-UPGRADE-CORE COMPLETE: 2026-04-28 20:35 | Surfaces: BOT / CONVERSATIONAL + TELEGRAM CHANNEL + PIPELINE / OPERATOR | Live Checked: partial | Benchmarks: 9 | OSS References: 8 | Improvements: 24 | Confidence: 84/100]

WHY CONFIDENCE IS NOT 100: нет production retention/engagement метрик; не был получен полный live dialog transcript из Telegram chat history; часть внешних benchmark-выводов опирается на public product pages, а не на глубокий paid/use-in-production pass.
