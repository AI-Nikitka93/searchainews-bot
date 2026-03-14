import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_config import get_models_dir, get_reports_dir


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("check_local_models")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def scan_files(base: Path, patterns: List[str]) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    if not base.exists():
        return results
    for pattern in patterns:
        for file in base.rglob(pattern):
            results.append(
                {
                    "path": str(file),
                    "name": file.name,
                    "size_gb": round(file.stat().st_size / 1024**3, 2),
                }
            )
    return results


def scan_ollama_models() -> List[Dict[str, str]]:
    ollama_dir = Path.home() / ".ollama" / "models"
    results = []
    if not ollama_dir.exists():
        return results
    for manifest in ollama_dir.rglob("manifest.json"):
        results.append({"path": str(manifest.parent)})
    return results


def check_ollama_updates() -> List[Dict[str, str]]:
    try:
        response = requests.get("https://ollama.com/api/tags", timeout=8)
        response.raise_for_status()
        data = response.json()
        updates = []
        for model in data.get("models", []):
            updates.append(
                {
                    "name": model.get("name"),
                    "size": model.get("size"),
                    "modified": model.get("modified_at"),
                    "family": model.get("details", {}).get("family"),
                }
            )
        return updates
    except Exception:
        return []


def main() -> None:
    logger = setup_logging()
    logger.info("Scanning local models...")

    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    manual_dir = get_models_dir()

    report = {
        "huggingface": scan_files(hf_cache, ["*.gguf", "*.safetensors"]),
        "ollama": scan_ollama_models(),
        "manual": scan_files(manual_dir, ["*.gguf", "*.safetensors", "*.bin"]),
        "ollama_updates": check_ollama_updates(),
    }

    reports_dir = get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "local_models_report.json"
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    logger.info("Report saved: %s", path)


if __name__ == "__main__":
    main()
