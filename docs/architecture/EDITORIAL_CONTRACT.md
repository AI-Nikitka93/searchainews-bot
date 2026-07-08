# EDITORIAL_CONTRACT

**Дата:** 2026-04-29  
**Статус:** `DONE`  
**Тип:** architecture handoff artifact  
**ACTIVE MODULES:** `M1 ARCHITECTURE SHAPE`, `M2 DATA FLOW & CONTRACTS`, `M3 NFR & OPERABILITY`, `M4 IMPLEMENTATION PATH`

## SUMMARY

SearchAInews сейчас живёт с двумя разными editorial-движками:

- канал уже использует source-aware ranking, topic-level dedupe и AI rewrite;
- бот всё ещё использует упрощённый role filter, слабый title-based dedupe и длинный item-per-message формат.

Это создаёт три системных дефекта:

1. **Role drift:** UI бота уже живёт на 4 ролях, а БД, analyzer и delivery код всё ещё держат старую смешанную таксономию.
2. **Story drift:** одна и та же история может прийти пользователю как 2-3 отдельных сообщения из разных источников, хотя канал уже умеет их схлопывать.
3. **Message drift:** канал выдаёт компактный редакционный блок, а бот — длинный “сырой” item card.

Этот контракт вводит **единое editorial ядро** для bot + channel:

- одна каноническая таксономия ролей;
- один shared ranking;
- один shared `topic_key`;
- один shared story clustering contract;
- отдельные delivery surfaces для канала и личного digest, но на общей editorial truth.

Главное архитектурное решение:

`Service decomposition not needed: modular monolith is sufficient because bot, channel, analyzer and persistence already live inside one Cloudflare Worker + D1 system, and the drift is caused by duplicated editorial logic rather than by missing service boundaries.`

---

## CORE ARCHITECTURE DECISION

Вместо независимых логик `channel.ts` и `news.ts` система должна перейти на **shared editorial core**.

### Decision

Нужен единый внутренний контракт:

- `Canonical Role`
- `Role Normalization`
- `Editorial Candidate`
- `Story Cluster`
- `Editorial Ranking`
- `Digest Rendering Contract`

### Why this

- Канал уже содержит более сильную логику отбора и подавления дублей.
- Бот не должен выдумывать собственные правила качества.
- Разрыв не в infra, а в duplicated editorial heuristics.

### Rejected alternative

Держать две отдельные логики и “подтягивать” бот точечными патчами.

Почему отклонено:

- это оставит второй источник истины;
- role drift вернётся;
- ranking drift вернётся;
- объяснимость персонализации останется слабой.

### Main trade-off

- Плюс: единое качество и меньше дрейфа.
- Минус: `news.ts` и `broadcast.ts` станут толще по данным и будут вынуждены работать не с raw items, а с story clusters.

---

## CONFIRMED / ASSUMPTION / OPEN QUESTION

### CONFIRMED

- UI бота сейчас использует 4 роли: `ai_specialist`, `ai_developer`, `ai_enthusiast`, `ai_beginner`.
- В `cf_worker/src/services/channel.ts` уже есть source-aware ranking, `topic_key`-логика и clustering heuristics.
- В `cf_worker/src/services/news.ts` и `cf_worker/src/services/broadcast.ts` сейчас используется отдельная упрощённая логика roleAliases + title/domain dedupe.
- Текущий bot message format строится через `formatItemMessage(...)` и выводит `Impact + Why + Action items + Source`.
- `deliveries` хранит доставку по `user_id + item_id`, а не по story/topic.

### ASSUMPTION

- Исторические записи с `target_role = ml_engineer / ops / pm / founder / other / null` всё ещё могут существовать в D1.
- Для первой реализации достаточно вычислять `topic_key` on-the-fly из полей `title + raw_summary + impact_rationale`, без немедленного добавления нового столбца в БД.
- Для первой реализации можно переиспользовать current D1 tables без новой миграции.

### OPEN QUESTION

- Нужен ли во второй фазе persisted `topic_key` или `delivery_story_keys` для ускорения и аналитики. Для этого контракта ответ: **не обязателен в фазе 1**.

---

## ARCHITECTURE SPEC CARD

| Поле | Решение |
|---|---|
| Architecture Pattern | Modular monolith inside Cloudflare Worker + D1 |
| Communication Pattern | In-process shared editorial contract, not separate services |
| Data Pattern | D1 `items` as source of truth, derived story clusters in memory |
| Deployment Pattern | One Worker runtime, one D1 database, shared delivery logic |
| Primary Data Stores | `items`, `deliveries`, `users`, `channel_posts`, `channel_post_keys` |
| Failure Hotspots | role normalization drift, duplicate story delivery, weak fallback ranking, long message formatting |

---

## MODULE BOUNDARIES

## 1. Ingestion & Analysis

**Current owners:** `ingest.ts`, `ai_analyzer.ts`  
**Responsibility:** собрать item, проставить impact/rationale/actions/target_role.

**Must own:**

- raw article payload;
- `impact_score`;
- `impact_rationale`;
- `action_items_json`;
- original `target_role`.

**Must not own:**

- конечную пользовательскую роль в bot surface;
- финальный digest format;
- topic-level delivery dedupe.

## 2. Shared Editorial Core

**New logical owner:** shared contract layer, future reusable module for bot + channel.

**Responsibility:**

- нормализовать роли;
- ранжировать кандидатов;
- группировать story-level duplicates;
- выдавать унифицированную структуру `EditorialStory`.

**Public surface:**

- `normalizeRole(rawRole) -> CanonicalRole | fallback bucket`
- `rankCandidates(items, context) -> RankedItem[]`
- `clusterStories(items) -> EditorialStory[]`
- `buildTopicKey(item) -> string`
- `buildRoleReason(story, role) -> string`

**Forbidden coupling:**

- не зависит от grammY;
- не зависит от Telegram send API;
- не зависит от channel-only formatting.

## 3. Bot Delivery Surface

**Current owners:** `news.ts`, `broadcast.ts`, `bot.ts`, `utils/text.ts`

**Responsibility:**

- запросить editorial candidates для роли;
- собрать personal digest;
- отправить digest пользователю;
- отметить все item_ids внутри story cluster как доставленные.

**Must not own:**

- собственную отдельную dedupe logic;
- собственный отдельный ranking policy;
- отдельную устаревшую role taxonomy.

## 4. Channel Delivery Surface

**Current owner:** `channel.ts`

**Responsibility:**

- публичная каналовая упаковка;
- breaking/model-release режимы;
- channel-specific cadence rules.

**Must keep:**

- richer source ranking;
- topic-key memory;
- official > expert > media > community bias.

**Must not leak:**

- channel-specific cadence constraints в user digest;
- channel-only heuristics как замену role personalization.

---

## DATA FLOWS & CONTRACTS

## A. Unified Role Taxonomy

### Canonical roles

Это единственные допустимые user-facing роли:

| Canonical role | RU label | Смысл |
|---|---|---|
| `ai_specialist` | Специалист по ИИ | deep technical / research / ML-heavy |
| `ai_developer` | Разработчик ИИ | builder / integrator / shipping engineer |
| `ai_enthusiast` | Любитель ИИ | informed non-specialist / broad market-aware user |
| `ai_beginner` | Новичок в ИИ | early-stage learner |

### Normalization rule

Все входящие роли из БД, analyzer и legacy code перед выдачей нормализуются к 4 canonical roles.

| Raw role / source value | Canonical role | Why |
|---|---|---|
| `ai_specialist` | `ai_specialist` | already canonical |
| `ai_developer` | `ai_developer` | already canonical |
| `ai_enthusiast` | `ai_enthusiast` | already canonical |
| `ai_beginner` | `ai_beginner` | already canonical |
| `developer` | `ai_developer` | builder profile |
| `ml_engineer` | `ai_specialist` | deeper model/inference/research relevance than general app-dev |
| `ops` | `ai_developer` | closest practical role: deployment/runtime/operator-builder |
| `pm` | `ai_enthusiast` | broad product-interest role, no longer canonical specialist bucket |
| `founder` | `ai_enthusiast` | broad strategic consumer of AI news |
| `other` | `ai_enthusiast` | safest neutral default, not “beginner by accident” |
| `null` / empty | `ai_enthusiast` fallback pool | neutral fallback when role absent |

### Hard rule

Пользовательский интерфейс, `users.role`, analyzer output interpretation и delivery selection больше не имеют права жить на разных role maps.

One source of truth:

- user chooses one of 4 canonical roles;
- all inbound legacy roles are normalized into one of these 4 before ranking and delivery.

## B. Shared Ranking Algorithm

Бот должен использовать тот же смысл ranking, что и канал, но с персональным role-fit слоем сверху.

### Candidate input contract

Для unified ranking bot-side candidate должен содержать минимум:

- `id`
- `source_id`
- `title`
- `url`
- `raw_summary`
- `impact_score`
- `impact_rationale`
- `action_items_json`
- `target_role`
- `published_at / created_at`

### Selection stages

#### Stage 1 — Fetch

Bot fetch не должен сразу резать выборку до 3 raw items.

Новый принцип:

- брать расширенный candidate pool;
- сначала строить stories;
- только потом резать до digest size.

Рекомендуемый fetch:

- exact-role + neutral fallback candidates;
- свежесть `NEWS_MAX_AGE_HOURS`;
- `impact_score >= 3`;
- pool size не меньше `max(12, digest_limit * 4)`.

#### Stage 2 — Role normalization

Для каждого item:

- `normalized_target_role = normalizeRole(item.target_role)`

#### Stage 3 — Base editorial score

Нужно адаптировать channel-style ranking:

`editorial_score = impact_weight + source_quality_bonus + actionability_bonus + rationale_bonus + recency_bonus - repetition_penalties`

### Source quality policy

Shared source classes остаются такими же по смыслу, как в `channel.ts`:

- `official`
- `expert`
- `media`
- `community`
- `other`

### Priority order

Bot ranking должен наследовать channel-priority:

`official > expert > media > community`

Это означает:

- official / vendor / release-note / primary-source stories поднимаются вверх;
- media summary ниже official, если речь об одной и той же истории;
- forum/community stories без сильного practical value опускаются вниз.

#### Stage 4 — Personal fit layer

После editorial score применяется role-fit multiplier:

| Fit class | Правило | Effect |
|---|---|---|
| Exact | normalized target role == user role | highest priority |
| Neutral | normalized target role came from `other/null` | allowed, but below exact |
| Adjacent | manually allowed adjacency only when exact pool is thin | below exact, above random fallback |

### Adjacency policy

Минимальная adjacency policy:

| User role | Allowed adjacent overflow |
|---|---|
| `ai_specialist` | `ai_developer` |
| `ai_developer` | `ai_specialist` |
| `ai_enthusiast` | none by default; prefers neutral fallback |
| `ai_beginner` | none by default; prefers simplified exact/neutral items |

Цель:

- не ломать personalization случайной cross-role выдачей;
- но не делать digest пустым, если exact-role pool узок.

## C. Story Clustering Contract

### Problem

Сейчас bot delivery может выдать три item-а про одну и ту же новость. Канал уже борется с этим через topic-level logic.

### Decision

Бот должен работать не с `NewsItem[]`, а с `EditorialStory[]`.

### EditorialStory shape

```ts
type EditorialStory = {
  topic_key: string
  main_item: Item
  related_items: Item[]
  source_class: "official" | "expert" | "media" | "community" | "other"
  normalized_target_role: CanonicalRole
  why_this_role: string
}
```

### Clustering rule

Использовать channel-style topic logic:

- `source_dedupe_key = host + normalized_title`
- `topic_key = fingerprint(top tokens from title + raw_summary + impact_rationale)`
- stories merge when:
  - same `topic_key`, or
  - high token overlap / same story fingerprint

### Main item selection inside cluster

Главным item в story должен становиться лучший источник по editorial ranking:

`official` beats `expert`, `expert` beats `media`, `media` beats `community`.

Если secondary source полезен:

- он не превращается в отдельное сообщение;
- он попадает в `related_items`.

### User-facing result

Вместо:

- 3 сообщения про один и тот же Anthropic/OpenAI release

Пользователь видит:

- 1 digest block
- 1 главный источник
- дополнительные ссылки `Еще источники`

## D. Deduplication Policy

### In-session dedupe

Внутри одного `/latest` или одного scheduled digest:

- одна `EditorialStory` = один блок;
- один `topic_key` = не более одного блока.

### Cross-delivery dedupe

При формировании нового digest бот должен исключать story, если:

- пользователь уже получал item с тем же `topic_key` в dedupe window.

### Phase 1 implementation without schema change

Для delivered history:

1. взять последние delivery items пользователя за lookback window;
2. подтянуть соответствующие `items`;
3. вычислить их `topic_key` on-the-fly;
4. исключить новые candidates с тем же `topic_key`.

### Phase 2 optional optimization

Если later performance/history станет проблемой:

- ввести persisted story-key memory для user delivery.

Но это **не нужно для первой реализации**.

## E. Message Design Contract — Personal Digest

### Goal

Bot message должен стать коротким, понятным и объясняющим, почему новость пришла именно этому человеку.

### New block format

Каждая story в personal digest:

```md
<Заголовок RU>
<1-2 предложения: что произошло и почему важно>
Почему это вам: <роль-ориентированная строка>
Что сделать: <ровно один action item>
Источник: <главная ссылка>
Еще источники: <0-2 ссылки, если story cluster > 1>
```

### Hard formatting rules

- Заголовок всегда один.
- Summary максимум 1-2 предложения.
- Action item ровно один, самый сильный.
- `Почему это вам:` обязателен всегда.
- Если related sources нет, строка `Еще источники` не выводится.
- Если action items нет, берётся краткий next-best practical takeaway из rationale, а не выводится пустой bullet wall.

### Role explanation line

`Почему это вам:` не должен быть generic filler.

Он обязан объяснять связь между story и ролью.

Примеры формата:

- `Почему это вам: это влияет на выбор моделей, стек и инженерные решения для AI-разработки.`
- `Почему это вам: это сигнал о новых возможностях и ограничениях, которые важны для глубокой AI-практики.`
- `Почему это вам: это даёт понятный ориентир по важным AI-сдвигам без лишнего шума.`
- `Почему это вам: это помогает учиться на действительно значимых новостях, а не на случайном хайпе.`

### Digest container format

Для `/latest` и scheduled personal delivery рекомендуется не “по одному item в отдельном сообщении”, а один digest message с 2-3 story blocks:

```md
<Короткий заголовок digest>

1) <Story block A>

2) <Story block B>

3) <Story block C>
```

Это снижает spam feel и приближает бота к editorial quality канала.

---

## NFR & OPERABILITY

| NFR | Why it matters | Architectural implication | What breaks if ignored |
|---|---|---|---|
| Consistency | bot и channel должны говорить одной editorial truth | shared core ranking + topic_key + role normalization | channel умный, bot глупый |
| Relevance | пользователь ждёт personal fit | exact-role first, neutral fallback second, adjacency last | бот кажется шумным и случайным |
| Compression | digest не должен быть простынёй | story clustering + one-block format | fatigue, lower read rate |
| Explainability | пользователь должен понять, почему это ему пришло | mandatory `Почему это вам:` line | personalization выглядит фальшивой |
| Maintainability | drift нельзя чинить в 3 местах руками | shared contract instead of duplicated heuristics | повторный architectural drift |
| Performance | Worker не должен превращать `/latest` в тяжёлый аналитический job | wide fetch but bounded pool, in-memory clustering | latency / cost spikes |
| Observability | нужно понимать, почему story выбрана или отброшена | log role normalization, cluster size, fallback usage | сложно отлаживать relevance debt |

### Required observability signals

После реализации editorial core должен логировать:

- raw role -> canonical role normalization;
- candidate count before/after clustering;
- stories dropped by topic dedupe;
- fallback mode used: exact / neutral / adjacent;
- number of related sources attached to each story.

---

## IMPLEMENTATION PATH

## Phase 1 — Freeze the contract

**Goal:** зафиксировать shared editorial truth без кода в нескольких местах.  
**Done criterion:** этот документ принят как источник истины для bot/channel editorial layer.  
**Main dependency:** понимание текущего `channel.ts`, `news.ts`, `broadcast.ts`.  
**Main risk:** пытаться чинить drift точечными alias-патчами без shared contract.

## Phase 2 — Shared data contract in `services/news.ts`

**Goal:** `news.ts` перестаёт возвращать raw deduped items и начинает собирать role-aware `EditorialStory[]`.  
**Done criterion:** `getLatestForRole(...)` использует canonical role normalization, wider candidate fetch, shared ranking и story clustering.  
**Main dependency:** query must include `source_id`, `raw_summary`, timestamps.  
**Main risk:** сохранить старый SQL shape и не дать ranking нужных данных.

### Required changes in `services/news.ts`

1. Расширить SELECT:
   - добавить `source_id`
   - добавить `raw_summary`
   - сохранить `published_at/created_at`

2. Удалить старую локальную `roleAliases` модель как source of truth.

3. Ввести pipeline:
   - fetch candidates
   - normalize roles
   - score candidates
   - cluster into stories
   - exclude by delivered `topic_key`
   - trim to digest size

4. Вернуть не просто `NewsItem[]`, а contract-friendly story structure или pre-renderable digest blocks.

## Phase 3 — Delivery rewrite in `services/broadcast.ts`

**Goal:** scheduled bot delivery использует ту же editorial logic, что и `/latest`.  
**Done criterion:** `runBroadcast(...)` отправляет personal digest blocks, а не 3 independent raw item cards.  
**Main dependency:** `news.ts` shared editorial output.  
**Main risk:** сделать clustering only for `/latest`, leaving scheduled delivery stale.

### Required changes in `services/broadcast.ts`

1. Перестать дублировать local dedupe helpers.
2. Получать уже clustered/ranked stories из shared editorial layer.
3. Отправлять один digest container message вместо цикла “1 item = 1 message”, если это не breaking/urgent scenario.
4. После отправки помечать delivered:
   - `main_item.id`
   - все `related_items[].id`

Это важно: иначе related source не ушёл в чат, но будет снова показан как “новая история”.

## Phase 4 — Message rendering contract

**Goal:** внедрить new digest format в `utils/text.ts` или новый renderer рядом.  
**Done criterion:** у bot digest есть compact block format с `Почему это вам:`.  
**Main dependency:** `EditorialStory` contract.  
**Main risk:** оставить old `Impact/Why/Action items` wall alongside new clustering.

## Phase 5 — Analyzer and type cleanup

**Goal:** убрать новый drift на входе.  
**Done criterion:** analyzer и shared types больше не производят/не поддерживают старую public taxonomy как норму.  
**Main dependency:** принятие canonical role map.  
**Main risk:** delivery слой нормализует старые роли, но analyzer продолжает их генерировать.

### Minimal follow-up beyond requested files

Хотя этот шаг сфокусирован на `news.ts` и `broadcast.ts`, для полного устранения drift потом потребуются точечные follow-up changes в:

- `services/ai_analyzer.ts`
- `types.ts`
- `bot.ts`

Причина:

- иначе публичная роль и внутренний role union останутся разъехавшимися.

---

## ARCHITECTURAL RISKS

1. **Half-migration risk**  
Если обновить только `/latest`, а `runBroadcast` оставить на старой логике, drift останется.

2. **Raw item persistence bias**  
Если по delivery продолжать мыслить `item_id`, а не `story/topic`, дубли по одной истории вернутся.

3. **Fallback flood risk**  
Если `other/null` items поднимать слишком высоко, personalization превратится в шум.

4. **Renderer drift risk**  
Если clustering будет новым, а `formatItemMessage` останется старым raw-card renderer, digest всё ещё будет выглядеть как простыня.

5. **Analyzer-output drift**  
Если analyzer продолжит считать `pm/founder/developer` нормальными публичными ролями, normalization contract останется repair-layer instead of source-layer.

---

## HANDOFF

### First implementation phase

Начинать с shared editorial extraction inside `services/news.ts`.

### Module order

1. shared role normalization + source classification helpers  
2. shared topic key + clustering  
3. `news.ts` fetch/rank/cluster  
4. `broadcast.ts` digest delivery  
5. renderer update  
6. analyzer/type cleanup

### Must-not-break constraints

- не ломать current D1 schema в phase 1;
- не ломать channel-specific breaking/model-release paths;
- не превращать `/latest` в unbounded heavy query;
- не терять `deliveries` semantics.

### Test-critical zones

- exact role match vs fallback role match
- `pm/founder/developer/ml_engineer/ops` normalization
- one-story-many-sources clustering
- cross-delivery duplicate suppression by `topic_key`
- digest rendering with and without action item
- marking all cluster item_ids as delivered

---

## FINAL THESIS

SearchAInews не нужен новый сервис и не нужна новая сложная distributed архитектура. Ему нужен один **shared editorial contract**, который сделает bot таким же умным, как channel, но не потеряет personal relevance.

Если коротко:

- **канал уже умеет редактуру;**
- **бот уже умеет персонализацию;**
- **новый shared editorial core должен объединить эти два качества в одну систему.**
