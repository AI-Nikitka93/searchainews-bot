import argparse
import json
import os
from typing import List, Dict

import requests


def build_commands(lang: str) -> List[Dict[str, str]]:
    if lang == "ru":
        return [
            {"command": "start", "description": "Старт и выбор языка/роли"},
            {"command": "menu", "description": "Показать меню"},
            {"command": "latest", "description": "Последние новости"},
            {"command": "settings", "description": "Настройки"},
            {"command": "role", "description": "Выбрать роль"},
            {"command": "language", "description": "Сменить язык"},
            {"command": "subscribe", "description": "Включить рассылку"},
            {"command": "unsubscribe", "description": "Отключить рассылку"},
            {"command": "about", "description": "О боте"}
        ]
    return [
        {"command": "start", "description": "Start and choose language/role"},
        {"command": "menu", "description": "Show menu"},
        {"command": "latest", "description": "Latest news"},
        {"command": "settings", "description": "Settings"},
        {"command": "role", "description": "Choose role"},
        {"command": "language", "description": "Change language"},
        {"command": "subscribe", "description": "Enable delivery"},
        {"command": "unsubscribe", "description": "Disable delivery"},
        {"command": "about", "description": "About the bot"}
    ]


def set_commands(bot_token: str, lang: str, dry_run: bool) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    payload = {"commands": build_commands(lang), "language_code": lang}
    if dry_run:
        print(f"[dry-run] {url}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"setMyCommands failed ({lang}): {resp.status_code} {resp.text}")
    print(f"setMyCommands ok ({lang})")


def set_menu_button(bot_token: str, dry_run: bool) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/setChatMenuButton"
    payload = {"menu_button": {"type": "commands"}}
    if dry_run:
        print(f"[dry-run] {url}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code >= 300:
        raise RuntimeError(f"setChatMenuButton failed: {resp.status_code} {resp.text}")
    print("setChatMenuButton ok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure Telegram bot commands/menu.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        print("BOT_TOKEN missing in environment.")
        return 1

    set_commands(bot_token, "ru", args.dry_run)
    set_commands(bot_token, "en", args.dry_run)
    set_menu_button(bot_token, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
