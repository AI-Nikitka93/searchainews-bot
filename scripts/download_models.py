import hashlib
import logging
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_config import get_models_dir


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("download_models")
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    logger = setup_logging()

    url = os.getenv("MODEL_URL", "").strip()
    expected = os.getenv("MODEL_SHA256", "").strip().lower()
    filename = os.getenv("MODEL_FILENAME", "").strip()

    if not url or not expected:
        logger.warning("MODEL_URL and MODEL_SHA256 must be set.")
        return

    if not filename:
        filename = url.split("/")[-1]

    target_dir = get_models_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    logger.info("Downloading: %s", url)
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        with target_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)

    actual = sha256_file(target_path)
    if actual != expected:
        logger.warning("SHA256 mismatch. Expected %s, got %s", expected, actual)
        target_path.unlink(missing_ok=True)
        return

    logger.info("Downloaded OK: %s", target_path)


if __name__ == "__main__":
    main()
