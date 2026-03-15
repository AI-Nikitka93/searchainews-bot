Дата: 2026-03-15 22:05

Commit: 3424a1a6bc25e67f6364e4b2618ee3ea5d66f41e
Repo: SearchAInews

Конфигурация
- db_path: ${LOCALAPPDATA}/SearchAInews/data/news.db
- sources_count: 32
- worker_entrypoint: cf_worker/src/index.ts
- local_bot_entrypoint: bot/main.py
- pipeline: .github/workflows/pipeline.yml

Цель снапшота
- Зафиксировать исходное состояние перед шагами стабилизации.
