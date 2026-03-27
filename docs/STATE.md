STATUS: WORKING
Состояние: основной pipeline и Cloudflare Worker восстановлены, свежие новости снова собираются, анализируются и отправляются в D1.
Что сломалось: GitHub Actions не стартовали для private-репозитория из-за account billing/spending limit; из-за этого scrape/analyze/push не выполнялись, канал перестал получать новые items.
Что уже сделано:
- Репозиторий переведён в public, чтобы снять блокировку GitHub Actions для текущего сценария.
- Добавлена лицензия All Rights Reserved и обновлён README с прямым запретом на использование без письменного разрешения автора.
- Выполнен аудит tracked-файлов и git history на предмет .env / cf_worker/.dev.vars; явных утечек секретов не найдено.
- Wrangler перелогинен в правильный Cloudflare-аккаунт Georgaishkin@gmail.com и Worker успешно задеплоен.
- На Worker включена более строгая защита webhook: ALLOW_WEBHOOK_WITHOUT_SECRET=false.
- GitHub Actions run 23667757742 завершился success: Scrape sources -> Analyze items -> Push to Cloudflare Worker.
- В remote D1 после восстановления есть свежие items и кандидаты для канала; ручная проверка channel-broadcast показала skip не из-за ошибки, а из-за окна публикации 09-23 по Минску.
Что важно помнить следующему агенту:
- Канал может молчать ночью штатно: cf_worker/wrangler.toml задаёт CHANNEL_ACTIVE_HOURS = "09-23".
- GitHub pipeline работает ежечасно по .github/workflows/pipeline.yml, Worker cron тоже ежечасный.
- Остаточный риск не устранён полностью: OpenRouter местами отвечает 429 и 402 Payment Required, но последний успешный run всё равно обновил 34 items и запушил их в Worker.
- Для Cloudflare deploy нужен аккаунт Georgaishkin@gmail.com; неверный аккаунт aiomdurman@gmail.com давал Authentication error 10000.
