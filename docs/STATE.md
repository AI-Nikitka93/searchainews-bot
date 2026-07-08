STATUS: BLOCKED
Состояние на 2026-05-31: Cloudflare Worker, Telegram webhook и remote D1 доступны, но production-новости устарели. Главный активный blocker теперь не Cloudflare auth, а отключённый GitHub Actions workflow `pipeline` (`disabled_inactivity`), из-за чего scheduled ingestion не пополняет D1 свежими items.
Активный шаг: явно включить GitHub Actions workflow `pipeline.yml`, запустить свежий ingestion/analyze/push run и после этого проверить `/latest`, канал и remote D1 freshness.
BLOCKER: `gh workflow list --all` показывает `pipeline disabled_inactivity`; remote D1 содержит `items_total=2906`, `scored_total=2906`, но `latest_item_ts=2026-05-26T21:40:16+00:00`, а при рабочем окне `NEWS_MAX_AGE_HOURS=36` сейчас `eligible_latest_36h=0`.
Что уже сделано:
- Репозиторий переведён в public, чтобы снять блокировку GitHub Actions для текущего сценария.
- Добавлена лицензия All Rights Reserved и обновлён README с прямым запретом на использование без письменного разрешения автора.
- Выполнен аудит tracked-файлов и git history на предмет .env / cf_worker/.dev.vars; явных утечек секретов не найдено.
- Подтверждено, что проект Worker привязан к Cloudflare account `b3b247be02d9e58286eed750c6752e34`; текущая Wrangler-сессия теперь вошла в правильный аккаунт `georgaishkin@gmail.com`.
- `wrangler d1 migrations list searchainews --remote` возвращает `No migrations to apply`; remote D1 читается из текущего workspace.
- `.github/workflows/pipeline.yml` не содержит шага deploy Worker, поэтому один только git push не выносит изменения `cf_worker/src/*` в production.
- На Worker включена более строгая защита webhook: ALLOW_WEBHOOK_WITHOUT_SECRET=false.
- Исторический GitHub Actions run 23667757742 завершался success: Scrape sources -> Analyze items -> Push to Cloudflare Worker.
- Последний подтверждённый scheduled run `26477480035` был успешным 2026-05-26, но после него новых scheduled runs нет; remote D1 сейчас не содержит items в 36-часовом рабочем окне для `/latest` и канала.
Что важно помнить следующему агенту:
- Канал может молчать ночью штатно: cf_worker/wrangler.toml задаёт CHANNEL_ACTIVE_HOURS = "09-23".
- GitHub pipeline должен работать ежечасно по .github/workflows/pipeline.yml, но сейчас отключён `disabled_inactivity`; Worker cron остаётся ежечасным, но не заменяет Python scrape/analyze/push pipeline.
- Остаточный риск не устранён полностью: OpenRouter местами отвечает 429 и 402 Payment Required, но последний успешный run всё равно обновил 34 items и запушил их в Worker.
- Для Cloudflare deploy нужен аккаунт Georgaishkin@gmail.com; неверный аккаунт aiomdurman@gmail.com давал Authentication error 10000.
Текущий исследовательский статус на 2026-04-04:
- Выполнен web-audit источников для обновления config.yaml с акцентом на RSS/Atom и dev-first AI media.
- Подтверждено, что OpenAI ChatGPT / Model release notes не являются простой опечаткой в конфиге: direct fetch возвращает 403, а path через r.jina.ai ранее давал 451.
- Подтверждено, что VentureBeat FeedBurner endpoint технически деградировал: отвечает, но парсится как пустой/битый feed.
- Подтверждено, что NVIDIA Newsroom / Press Room RSS по-прежнему отвечает 403 и не подходит как надёжный источник для текущего scraper path.
- Собран shortlist свежих источников на замену и усиление coverage: Together AI RSS, Ollama RSS, vLLM RSS, Ai2 RSS, LangChain RSS, Cohere Blog, Cerebras Blog, Groq Blog, Replicate Blog, Modal Atom, Import AI, Interconnects и др.
Статус внедрения на 2026-04-04:
- В `config.yaml` отключены проблемные endpoints: `openai_chatgpt_release_notes`, `openai_model_release_notes`, `venturebeat_main`. `nvidia_press` остаётся отключённым.
- В `config.yaml` добавлены и перепроверены новые источники: `together_ai_blog`, `ollama_blog`, `vllm_blog`, `langchain_blog`, `ai2_research`, `replicate_blog`, `modal_blog`, `import_ai`, `interconnects_ai`, `ahead_of_ai`, `groq_blog`.
- `cerebras_blog` после внедрения был отключён обратно: текущий `listing_page` extraction регулярно возвращает заголовок `Cerebras` вместо названия статьи.
- Для `replicate_blog` добавлен `freshness_max_days: 120`, иначе источник оставался пустым при глобальном окне свежести 14 дней.
- Полный `scraper.py --config config.yaml` после обновления конфига завершился успешно и сохранил `274` items.
- Остаточный parser-risk после recheck: `techcrunch_feed` всё ещё иногда упирается в `r.jina.ai` с `451 Unavailable For Legal Reasons`, хотя сам pipeline не падает.
Статус downstream-проверки на 2026-04-04:
- Длинный `ai_analyzer.py --config config.yaml --limit 40` завершился успешно, но подтвердил архитектурный узкий момент: он обрабатывает общий priority backlog и коммитит изменения только в самом конце транзакции.
- По новым источникам за этот прогон реально были проанализированы `3` записи: `interconnects_ai=1`, `langchain_blog=1`, `vllm_blog=1`; ещё `34` записи новых source_id остаются без score.
- `python scripts/push_to_worker.py --config config.yaml --limit 200` успешно отправил `39` scored items в Cloudflare Worker и обновил `sync_state.json` до `last_id=1752`.
- После push хвост scored-элементов относительно sync frontier обнулился: `items WHERE impact_score IS NOT NULL AND id > 1752 = 0`.
Статус аудита контента канала на 2026-04-04:
- Полная история фактических текстов постов в репозитории не хранится: Worker сохраняет `channel_posts` только как `item_id + sent_at`, а AI-summary/translation генерируются на лету и не персистятся.
- Из-за текущего Cloudflare login mismatch (`wrangler` не авторизован к account проекта) прямое чтение remote D1 `channel_posts` недоступно без перелогина.
- Контент-аудит выполнен по актуальным scored items из локальной `news.db` и по фактической логике форматирования в `cf_worker/src/services/channel.ts`.
- Главные содержательные проблемы текущего channel-layer: заголовки часто остаются на английском, summaries иногда обрываются по лимиту символов посреди слова, а в выдаче доминируют агрегаторы/форумы (`reddit`, `HN`, `The Verge`) вместо более авторитетного первоисточника.
- Отдельный риск повторов по теме сохраняется: одна и та же история про Anthropic/OpenClaw присутствует сразу в нескольких scored items из разных источников.
Статус editorial refactor на 2026-04-04:
- Обновлён `prompts/analyzer.txt`: новый contract теперь developer-first, жёстче штрафует noise/community hype и требует 2–3 коротких предложения с practical impact.
- В `ai_analyzer.py` добавлены targeted-run по `--source-id`, промежуточные `commit` и выравнивание rationale до `<=320` символов / `<=3` предложений.
- В `cf_worker/src/services/channel.ts` усилены три слоя: AI rewrite теперь генерирует `title + summary` в JSON, selection ранжирует источники по качеству (`official > expert > media > community`), а dedupe хранит и source-key, и topic-key для лучшего подавления story-level повторов.
- Обычные channel posts теперь могут включать короткую строку `Что проверить:` для high-impact items вместо чисто описательного вывода.
- В `cf_worker/src/services/ai_analyzer.ts` обновлён prompt, чтобы Worker-side fallback не расходился с новым editorial standard.
- Адресная runtime-проверка прошла: `python ai_analyzer.py --config config.yaml --source-id together_ai_blog --limit 1` → `Updated items: 1`; запись `Wan 2.7 now available on Together AI` получила `impact_score=5`, `target_role=ai_developer`, осмысленный rationale и concrete action items.
- `python scripts/push_to_worker.py --config config.yaml --limit 5 --dry-run` после этого вернул `No new scored items to push`, то есть pipeline-state остался консистентным.
- Техническое ограничение на момент фиксации: полный `npx tsc --noEmit` в `cf_worker` всё ещё падает на старые repo-wide typing issues вне моей зоны (`bot.ts`, `index.ts`, `types.ts`, `ingest.ts`), но новые ошибки в изменённых `channel.ts` и `services/ai_analyzer.ts` не остались.
Следующий шаг:
- Разблокировать Cloudflare deploy: войти в аккаунт `Georgaishkin@gmail.com` для account `b3b247be02d9e58286eed750c6752e34` или предоставить валидный `CLOUDFLARE_API_TOKEN` с доступом к этому аккаунту и Workers/D1.
- После разблокировки сразу повторить `wrangler deploy src/index.ts` в `cf_worker` и подтвердить, что live Worker уже использует новый editorial contract.
- Затем отдельно проверить уже живые channel posts после следующего Worker cron и оценить результат на реальной выдаче.
