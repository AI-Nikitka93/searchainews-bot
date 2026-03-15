import json
import logging
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

from ai_config import (
    CLOUD_FALLBACK_ORDER,
    DEFAULT_CLOUD_MODELS,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OPENROUTER_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
    LLM_RETRY_BACKOFF_SECONDS,
    get_reports_dir,
)


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


def _get_vram_usage() -> Tuple[Optional[int], Optional[int]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0:
            return None, None
        line = result.stdout.strip().splitlines()[0]
        used_str, total_str = [part.strip() for part in line.split(",")]
        return int(used_str), int(total_str)
    except Exception:
        return None, None


class HybridLLMClient:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        repo_root = Path(__file__).resolve().parent
        _load_dotenv(repo_root / ".env")
        self.ollama_available = self._check_ollama_ready()
        self.last_provider: Optional[str] = None
        self.last_model: Optional[str] = None

    def _check_ollama_ready(self) -> bool:
        try:
            response = requests.get(
                f"{OLLAMA_HOST}/api/tags", timeout=5
            )
            if response.status_code != 200:
                self.logger.warning("Ollama not ready: status=%s", response.status_code)
                return False
            payload = response.json()
            models = {m.get("name") for m in payload.get("models", [])}
            if OLLAMA_MODEL not in models:
                self.logger.warning(
                    "Ollama model not found locally: %s. Available: %s",
                    OLLAMA_MODEL,
                    sorted(models),
                )
                return False
            return True
        except Exception as exc:
            self.logger.warning("Ollama check failed: %s", exc)
            return False

    def _log_inference(
        self,
        provider: str,
        model: str,
        backend: str,
        duration_s: float,
    ) -> None:
        used, total = _get_vram_usage()
        vram = "unknown"
        device = "cpu/unknown"
        if used is not None and total is not None:
            vram = f"{used}/{total}MB"
            device = "gpu"
        self.logger.info(
            "inference provider=%s model=%s backend=%s device=%s duration_s=%.2f vram=%s",
            provider,
            model,
            backend,
            device,
            duration_s,
            vram,
        )

    def _save_run_record(self, record: Dict[str, object]) -> None:
        reports_dir = get_reports_dir()
        reports_dir.mkdir(parents=True, exist_ok=True)
        path = reports_dir / "analysis_runs.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _ollama_chat(self, system_prompt: str, user_prompt: str) -> str:
        start = time.time()
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        duration = time.time() - start
        self._log_inference("local", OLLAMA_MODEL, "ollama", duration)
        self.last_provider = "local"
        self.last_model = OLLAMA_MODEL
        self._save_run_record(
            {
                "run_id": uuid.uuid4().hex,
                "provider": "local",
                "model": OLLAMA_MODEL,
                "backend": "ollama",
                "duration_ms": int(duration * 1000),
                "success": True,
            }
        )
        return content

    def _cloud_chat(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        last_error: Optional[Exception] = None
        for attempt in range(1, LLM_MAX_RETRIES + 1):
            start = time.time()
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else LLM_RETRY_BACKOFF_SECONDS * attempt
                except ValueError:
                    delay = LLM_RETRY_BACKOFF_SECONDS * attempt
                self.logger.warning(
                    "Rate limited by %s (attempt %s/%s). Sleeping %.1fs",
                    provider,
                    attempt,
                    LLM_MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                continue
            try:
                response.raise_for_status()
                data = response.json()
                break
            except Exception as exc:
                last_error = exc
                if attempt < LLM_MAX_RETRIES:
                    delay = LLM_RETRY_BACKOFF_SECONDS * attempt
                    self.logger.warning(
                        "LLM request failed (%s, attempt %s/%s). Sleeping %.1fs",
                        provider,
                        attempt,
                        LLM_MAX_RETRIES,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                raise
        else:
            if last_error:
                raise last_error
            raise RuntimeError("LLM request failed after retries.")

        content = data["choices"][0]["message"]["content"]
        duration = time.time() - start
        self._log_inference(provider, model, "cloud", duration)
        self.last_provider = provider
        self.last_model = model
        self._save_run_record(
            {
                "run_id": uuid.uuid4().hex,
                "provider": provider,
                "model": model,
                "backend": "cloud",
                "duration_ms": int(duration * 1000),
                "success": True,
            }
        )
        return content

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.ollama_available:
            try:
                return self._ollama_chat(system_prompt, user_prompt)
            except Exception as exc:
                self.logger.warning("Local model failed, switching to cloud: %s", exc)

        for provider in CLOUD_FALLBACK_ORDER:
            model = DEFAULT_CLOUD_MODELS.get(provider, "")
            if not model:
                self.logger.warning("Cloud model missing for %s; skipping", provider)
                continue
            if provider == "OPENROUTER":
                key = os.getenv("OPENROUTER_API_KEY", "")
                if not key:
                    self.logger.warning("OPENROUTER_API_KEY missing; skipping")
                    continue
                return self._cloud_chat(
                    "openrouter",
                    OPENROUTER_BASE_URL,
                    key,
                    model,
                    system_prompt,
                    user_prompt,
                )
            if provider == "MISTRAL":
                key = os.getenv("MISTRAL_API_KEY", "")
                if not key:
                    self.logger.warning("MISTRAL_API_KEY missing; skipping")
                    continue
                return self._cloud_chat(
                    "mistral",
                    "https://api.mistral.ai/v1",
                    key,
                    model,
                    system_prompt,
                    user_prompt,
                )
            if provider == "DEEPSEEK":
                key = os.getenv("DEEPSEEK_API_KEY", "")
                if not key:
                    self.logger.warning("DEEPSEEK_API_KEY missing; skipping")
                    continue
                return self._cloud_chat(
                    "deepseek",
                    "https://api.deepseek.com/v1",
                    key,
                    model,
                    system_prompt,
                    user_prompt,
                )
            if provider == "OPENAI":
                key = os.getenv("OPENAI_API_KEY", "")
                if not key:
                    self.logger.warning("OPENAI_API_KEY missing; skipping")
                    continue
                return self._cloud_chat(
                    "openai",
                    "https://api.openai.com/v1",
                    key,
                    model,
                    system_prompt,
                    user_prompt,
                )

        raise RuntimeError("No available LLM backend. Local and cloud providers unavailable.")
