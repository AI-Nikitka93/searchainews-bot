import os
from pathlib import Path
from typing import Optional

import yaml


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_load_dotenv(PROJECT_ROOT / ".env")


def get_db_path() -> str:
    config_path = PROJECT_ROOT / "config.yaml"
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    db_path = config.get("db_path")
    if not db_path:
        raise RuntimeError("db_path missing in config.yaml")
    return os.path.expandvars(db_path)


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "6297262714")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@AI_Nikitka93")

BOT_NAME = os.getenv("BOT_NAME", "AI Impact Radar")
BOT_SHORT = os.getenv("BOT_SHORT", "Actionable AI news with impact scoring for developers and PMs.")
BOT_WELCOME = os.getenv("BOT_WELCOME", "Hello! I analyze AI news and deliver actionable insights.")

LOG_PATH = os.getenv("BOT_LOG_PATH", os.path.expandvars(r"%LOCALAPPDATA%\SearchAInews\logs\bot.log"))

ROLE_OPTIONS = [
    ("developer", "Developer"),
    ("pm", "PM"),
    ("founder", "Founder"),
]

RATE_LIMIT_PER_SECONDS = float(os.getenv("RATE_LIMIT_PER_SECONDS", "1.0"))
RATE_LIMIT_BURST = int(os.getenv("RATE_LIMIT_BURST", "3"))


def get_webhook_url() -> Optional[str]:
    value = os.getenv("WEBHOOK_URL", "").strip()
    return value or None


WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
