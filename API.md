# API

## English

### Webhook (Telegram)
- **POST** `/webhook`  
Receives Telegram updates.

Example:
```bash
curl -X POST "<WORKER_URL>/webhook" \
  -H "X-Telegram-Bot-Api-Secret-Token: <WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":1,"type":"private"},"text":"/start"}}'
```

### Ingest
- **POST** `/ingest`  
Pushes parsed items into D1.

Headers:
- `X-Ingest-Token: <INGEST_SECRET>`

Body:
```json
{
  "items": [
    {
      "title": "Example",
      "url": "https://example.com",
      "raw_summary": "Short summary",
      "full_text": "Full text",
      "published_at": "2026-03-15T10:00:00Z"
    }
  ]
}
```

### Health
- **GET** `/health`  
Returns `ok`.

---

## Русский

### Webhook (Telegram)
- **POST** `/webhook`  
Принимает апдейты Telegram.

Пример:
```bash
curl -X POST "<WORKER_URL>/webhook" \
  -H "X-Telegram-Bot-Api-Secret-Token: <WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"update_id":1,"message":{"message_id":1,"chat":{"id":1,"type":"private"},"text":"/start"}}'
```

### Ingest
- **POST** `/ingest`  
Пушит новости в D1.

Заголовки:
- `X-Ingest-Token: <INGEST_SECRET>`

Тело:
```json
{
  "items": [
    {
      "title": "Example",
      "url": "https://example.com",
      "raw_summary": "Short summary",
      "full_text": "Full text",
      "published_at": "2026-03-15T10:00:00Z"
    }
  ]
}
```

### Health
- **GET** `/health`  
Возвращает `ok`.
