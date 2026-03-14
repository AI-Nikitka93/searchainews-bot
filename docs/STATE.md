STATUS: BLOCKED
Причина: GitHub отвергает GITHUB_TOKEN (invalid credentials). Нужен корректный PAT (fine-grained или classic) с правами на репозиторий.
Что уже сделано: Cloudflare Worker задеплоен, D1 настроен, webhook установлен, локальный Task Scheduler отключён, workflow для CI добавлен.
Нужно для разблокировки: создать корректный PAT и заменить GITHUB_TOKEN в .env. Варианты:
1) Fine-grained PAT: Repository access → Only `searchainews-bot`; Permissions: Contents (RW), Metadata (R), Workflows (RW).
2) Classic PAT: scopes `repo` и `workflow`.
Затем повторить push и настройку secrets в GitHub Actions.
