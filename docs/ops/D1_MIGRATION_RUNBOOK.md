# D1 Migration Ledger Recovery Runbook

Дата: 2026-04-29  
Проект: SearchAInews  
База: `searchainews`  
Cloudflare account: `b3b247be02d9e58286eed750c6752e34`

## Когда использовать

Используй этот runbook, если:

- `npx wrangler d1 migrations list searchainews --remote` показывает все migration files как `to be applied`;
- remote D1 при этом уже содержит рабочие таблицы;
- есть риск, что `wrangler d1 migrations apply --remote` упрётся в `table already exists` или другой DDL conflict.

Этот runbook рассчитан на сценарий:

- фактическая схема в remote D1 уже существует;
- сломан или пуст внутренний migration ledger `d1_migrations`;
- данные трогать нельзя.

## Что это значит технически

Cloudflare D1 хранит применённые миграции в таблице `d1_migrations`.  
По состоянию на `Wrangler 4.73.0` логика CLI создаёт таблицу вида:

```sql
CREATE TABLE IF NOT EXISTS d1_migrations(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT UNIQUE,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

После каждой миграции Wrangler записывает:

```sql
INSERT INTO d1_migrations (name) VALUES ('<migration-file-name>');
```

Если схема уже создана вручную или старыми SQL-запусками, а `d1_migrations` пустая или отсутствует, `wrangler d1 migrations list` будет считать все файлы неприменёнными.

## Жёсткие правила безопасности

1. Не запускай `wrangler d1 migrations apply --remote`, пока не доказана schema parity.
2. Сначала зафиксируй backup / restore point.
3. Не вставляй записи в `d1_migrations`, если хотя бы одна migration реально не отражена в схеме.
4. Если схема расходится с `schema.sql` или migration files, остановись и заводи отдельный repair step.

## Подготовка окружения

В PowerShell:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID="b3b247be02d9e58286eed750c6752e34"
cd M:\Projects\Bot\SearchAInews\cf_worker
```

Проверь auth:

```powershell
npx wrangler whoami
```

Ожидается account:

- `georgaishkin@gmail.com`
- `b3b247be02d9e58286eed750c6752e34`

## Шаг 1. Зафиксировать backup / restore point

### 1.1 Проверить backend D1 и bookmark

```powershell
npx wrangler d1 info searchainews
npx wrangler d1 time-travel info searchainews
```

Сохрани текущий bookmark в incident notes.

### 1.2 Экспортировать полную remote SQL-копию

```powershell
New-Item -ItemType Directory -Force .\tmp | Out-Null
npx wrangler d1 export searchainews --remote --output=.\tmp\searchainews_pre_ledger_fix.sql
npx wrangler d1 export searchainews --remote --output=.\tmp\searchainews_pre_ledger_fix_schema.sql --no-data
```

Это не заменяет Time Travel, но даёт отдельный SQL artifact для проверки.

## Шаг 2. Доказать фактическую схему remote D1

### 2.1 Проверить список таблиц

```powershell
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_list"
```

Минимально ожидаются:

- `users`
- `items`
- `deliveries`
- `webhook_logs`
- `bot_errors`
- `bot_events`
- `request_logs`
- `channel_posts`
- `channel_post_keys`
- `channel_report_state`
- возможно `d1_migrations`

### 2.2 Проверить ключевые таблицы по колонкам

```powershell
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('users')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('items')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('deliveries')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('webhook_logs')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('bot_errors')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('bot_events')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('request_logs')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('channel_posts')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('channel_post_keys')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA table_info('channel_report_state')"
```

### 2.3 Проверить индексы

```powershell
npx wrangler d1 execute searchainews --remote --command "PRAGMA index_list('items')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA index_list('deliveries')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA index_list('channel_posts')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA index_list('channel_post_keys')"
npx wrangler d1 execute searchainews --remote --command "PRAGMA index_list('users')"
```

### 2.4 Проверить SQL schema напрямую

```powershell
npx wrangler d1 execute searchainews --remote --command "SELECT name, sql FROM sqlite_schema WHERE type IN ('table','index') ORDER BY type, name"
```

### Stop condition

Если хотя бы одна из таблиц/колонок/индексов из `schema.sql` или migration files отсутствует, **остановись**.

В этом случае:

- не вставляй записи в `d1_migrations`;
- не запускай `migrations apply --remote`;
- подними отдельный repair incident на реальную schema drift.

## Шаг 3. Проверить сам migration ledger

### 3.1 Есть ли таблица `d1_migrations`

```powershell
npx wrangler d1 execute searchainews --remote --command "SELECT name FROM sqlite_schema WHERE type='table' AND name='d1_migrations'"
```

### 3.2 Что в ней лежит

```powershell
npx wrangler d1 execute searchainews --remote --command "SELECT id, name, applied_at FROM d1_migrations ORDER BY id"
```

### 3.3 Что думает Wrangler

```powershell
npx wrangler d1 migrations list searchainews --remote
```

Если таблица пустая или отсутствует, а schema parity уже доказана, можно чинить ledger.

## Шаг 4. Безопасно “закрыть” зависшие миграции

### 4.1 Создать SQL-файл для ledger repair

Создай файл `.\tmp\d1_mark_migrations_applied.sql`:

```sql
CREATE TABLE IF NOT EXISTS d1_migrations(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT UNIQUE,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_add_bot_errors.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_add_debug_logs.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_add_indexes.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_add_language.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_add_webhook_logs.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_15_expand_webhook_logs.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_16_add_channel_posts.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_16_add_channel_post_keys.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_16_add_channel_report_state.sql');
INSERT OR IGNORE INTO d1_migrations (name) VALUES ('2026_03_17_add_source_id.sql');
```

### Почему именно так

- `CREATE TABLE IF NOT EXISTS` безопасно создаёт ledger, если его нет.
- `INSERT OR IGNORE` не ломает повторный запуск.
- Мы не выполняем сами DDL migrations повторно.
- Мы только синхронизируем служебный migration ledger с уже доказанной схемой.
- Для `wrangler d1 execute --remote --file ...` не используй `BEGIN`, `COMMIT` или `SAVEPOINT`: Cloudflare может отклонить такой файл с ошибкой про транзакции. В этом сценарии безопаснее выполнять idempotent SQL без явной ручной транзакции.

### 4.2 Применить ledger repair

```powershell
npx wrangler d1 execute searchainews --remote --file=.\tmp\d1_mark_migrations_applied.sql
```

## Шаг 5. Доказать, что ledger починен

### 5.1 Повторно проверить ledger

```powershell
npx wrangler d1 execute searchainews --remote --command "SELECT id, name, applied_at FROM d1_migrations ORDER BY id"
```

### 5.2 Повторно проверить Wrangler view

```powershell
npx wrangler d1 migrations list searchainews --remote
```

Ожидаемое состояние:

- список `to be applied` пуст;
- `d1_migrations` содержит все текущие migration filenames;
- schema и data не менялись.

## Шаг 6. Что делать, если что-то пошло не так

### Если `d1_mark_migrations_applied.sql` не выполнился

1. Ничего не запускай повторно вслепую.
2. Сними текст ошибки.
3. Снова проверь:

```powershell
npx wrangler d1 execute searchainews --remote --command "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
npx wrangler d1 execute searchainews --remote --command "SELECT id, name, applied_at FROM d1_migrations ORDER BY id"
```

### Если после repair `migrations list` всё ещё показывает pending

Проверь:

1. что используешь именно database name `searchainews`;
2. что выставлен правильный `CLOUDFLARE_ACCOUNT_ID`;
3. что в `wrangler.toml` не переопределён `migrations_table`;
4. что filenames в `d1_migrations.name` совпадают с именами файлов в `cf_worker/migrations/` один в один.

### Если случайно применили неправильный SQL

Используй restore только по согласованному incident decision:

```powershell
npx wrangler d1 time-travel info searchainews
npx wrangler d1 time-travel restore searchainews --bookmark="<PREVIOUS_BOOKMARK>"
```

`time-travel restore` — destructive operation. Делай её только как rollback step с явным подтверждением.

## Чего делать нельзя

- Не выполнять `wrangler d1 migrations apply --remote` до проверки schema parity.
- Не дропать таблицы ради “очистки” ledger.
- Не редактировать `schema.sql` задним числом ради совпадения с продом.
- Не вставлять в `d1_migrations` имена миграций, которые реально не отражены в схеме.

## Короткий operator checklist

- [ ] Выставлен `CLOUDFLARE_ACCOUNT_ID`
- [ ] Проверен правильный Cloudflare account через `wrangler whoami`
- [ ] Снят `time-travel` bookmark
- [ ] Сделан SQL export remote D1
- [ ] Доказана schema parity через `PRAGMA` / `sqlite_schema`
- [ ] Проверено текущее состояние `d1_migrations`
- [ ] Выполнен только ledger repair, без повторного DDL
- [ ] `wrangler d1 migrations list searchainews --remote` после этого пуст

## Источники истины

- Cloudflare D1 migrations docs, проверено на `2026-04-29`
- Cloudflare D1 SQL statements docs, проверено на `2026-04-29`
- Cloudflare D1 Time Travel docs, проверено на `2026-04-29`
- Локальный `wrangler 4.73.0`, где зафиксирована структура `d1_migrations` и запись `INSERT INTO d1_migrations (name)`
