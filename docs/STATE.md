STATUS: BLOCKED
Причина: Telegram получает 401 от webhook — вероятно, WEBHOOK_SECRET в Cloudflare не совпадает с секретом в URL webhook. Требуется ручная синхронизация секрета в Cloudflare.
Что уже сделано: Диагностика показала 401 от Telegram, /health OK, debug endpoint OK; webhook reset выполнен.
Нужно для разблокировки: В Cloudflare Workers → Settings → Variables and Secrets обновить WEBHOOK_SECRET на значение из .env (или из текущего webhook URL), затем повторить setWebhook.
