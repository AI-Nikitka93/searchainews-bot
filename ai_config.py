import os
from pathlib import Path

APP_NAME = "SearchAInews"


def get_app_data_dir() -> Path:
    base = Path(os.path.expandvars(r"%LOCALAPPDATA%"))
    return base / APP_NAME


def get_log_path() -> Path:
    override = os.getenv("LOG_PATH")
    if override:
        return Path(os.path.expandvars(override))
    return get_app_data_dir() / "logs" / "app.log"


def get_reports_dir() -> Path:
    return get_app_data_dir() / "reports"


def get_models_dir() -> Path:
    return get_app_data_dir() / "models"


def get_prompt_path() -> Path:
    return Path(__file__).resolve().parent / "prompts" / "analyzer.txt"


DEFAULT_DB_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# Model sizing for VRAM budgeting (local default)
LOCAL_MODEL_PARAMS_B = float(os.getenv("LOCAL_MODEL_PARAMS_B", "7"))
LOCAL_MODEL_QUANT = os.getenv("LOCAL_MODEL_QUANT", "q4_k_m")
LOCAL_MODEL_N_CTX = int(os.getenv("LOCAL_MODEL_N_CTX", "4096"))

# Analyzer runtime limits
MAX_ITEMS_PER_RUN = int(os.getenv("MAX_ITEMS_PER_RUN", "20"))
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "16000"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))

# Safety budget for agent-like workloads
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
MAX_TOKENS_PER_RUN = int(os.getenv("MAX_TOKENS_PER_RUN", "50000"))
MAX_COST_USD = float(os.getenv("MAX_COST_USD", "1.0"))

# Cloud fallback order (only used if key + model are present)
CLOUD_FALLBACK_ORDER = [
    "OPENROUTER",
    "MISTRAL",
    "DEEPSEEK",
    "OPENAI",
]

DEFAULT_CLOUD_MODELS = {
    "OPENROUTER": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
    "MISTRAL": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
    "DEEPSEEK": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "OPENAI": os.getenv("OPENAI_MODEL", ""),
}

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def calculate_vram_budget(model_params_b: float, quantization: str, n_ctx: int) -> dict:
    if quantization == "f16":
        model_vram_gb = model_params_b * 2
    elif quantization == "q4_k_m":
        model_vram_gb = model_params_b * 0.7
    elif quantization == "q4_0":
        model_vram_gb = model_params_b * 0.5
    else:
        model_vram_gb = model_params_b * 1.0

    kv_cache_per_token_gb = model_params_b * 2 / 1024**2
    kv_cache_gb = kv_cache_per_token_gb * n_ctx
    activations_gb = model_params_b * 0.1
    total_vram_gb = model_vram_gb + kv_cache_gb + activations_gb

    return {
        "model_vram_gb": round(model_vram_gb, 2),
        "kv_cache_gb": round(kv_cache_gb, 2),
        "activations_gb": round(activations_gb, 2),
        "total_vram_gb": round(total_vram_gb, 2),
    }
