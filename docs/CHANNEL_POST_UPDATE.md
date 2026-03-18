# Изменения логики постинга канала — 2026-03-18

## Что изменилось

### До
- **Модели/релизы** — постятся сразу (одна новость) ✅
- **Обычные новости** — постятся раз в 5 минут пачками по 2-5 новостей ❌

### После
- **Модели/релизы** — постятся сразу (одна новость) ✅
- **Обычные новости** — постятся **раз в час** пачками по **3 новости** ✅

## Изменённые файлы

1. **cf_worker/src/services/channel.ts**
   - `DEFAULT_GAP_SECONDS`: 300 → 3600 (5 мин → 1 час)
   - `DEFAULT_POST_MIN_ITEMS`: 2 → 3
   - `DEFAULT_POST_MAX_ITEMS`: 5 → 3

2. **cf_worker/wrangler.toml**
   - Добавлено: `CHANNEL_MODEL_RELEASE_ONE_BY_ONE = "true"`
   - Обновлён `CHANNEL_POST_GAP_SECONDS = "3600"`

3. **cf_worker/DEPLOY.md**
   - Добавлена секция о логике постинга канала

4. **docs/CHANGELOG.md**
   - Добавлена запись об изменениях

## Как задеплоить

### Вариант 1: Через wrangler (требуется OAuth)
```bash
cd "M:\Projects\Bot\SearchAInews\cf_worker"
npx wrangler login
npx wrangler deploy src/index.ts
```

### Вариант 2: Через Cloudflare Dashboard
1. Открыть https://dash.cloudflare.com/
2. Workers & Pages → searchainews-bot
3. Editor → скопировать содержимое `src/services/channel.ts`
4. Deploy

### Вариант 3: Через GitHub Actions
1. Закоммитить изменения
2. Push в GitHub
3. GitHub Actions автоматически задеплоит

## Как проверить

1. **Модель/релиз**: Должна выйти одна новость сразу при появлении
2. **Обычные новости**: Должны выходить раз в час по 3 новости в одном посте

## Логи

Cloudflare Workers → Logs → searchainews-bot

Или через CLI:
```bash
npx wrangler tail searchainews-bot
```

Ключевые сообщения:
- `channel_model_release_sent` — модель/релиз отправлена
- `channel_breaking_sent` — breaking новость отправлена
- `channel_sent` — обычные новости отправлены (count: 3)
- `channel_rate_limit` — пропуск из-за gap (3600 сек)
