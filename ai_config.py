import os
from pathlib import Path

APP_NAME = "SearchAInews"

def _parse_env_list(name: str, default: str = "") -> list:
    raw = os.getenv(name, default)
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


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
MAX_COMPRESSED_CHARS = int(os.getenv("MAX_COMPRESSED_CHARS", "6000"))
MAX_DISCUSSION_CHARS = int(os.getenv("MAX_DISCUSSION_CHARS", "1000"))
MAX_TOTAL_PROMPT_INPUT_CHARS = int(os.getenv("MAX_TOTAL_PROMPT_INPUT_CHARS", "5500"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
LLM_THROTTLE_SECONDS = float(os.getenv("LLM_THROTTLE_SECONDS", "4.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF_SECONDS = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "4.0"))
MIN_RATIONALE_CHARS = int(os.getenv("MIN_RATIONALE_CHARS", "60"))
MIN_ACTION_ITEMS = int(os.getenv("MIN_ACTION_ITEMS", "2"))
MAX_ACTION_ITEMS = int(os.getenv("MAX_ACTION_ITEMS", "3"))
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", "1024"))
ALLOWED_ROLES = _parse_env_list(
    "ALLOWED_ROLES",
    "ai_specialist,ai_developer,ai_enthusiast,ai_beginner,developer,pm,founder,other",
) or [
    "ai_specialist",
    "ai_developer",
    "ai_enthusiast",
    "ai_beginner",
    "developer",
    "pm",
    "founder",
    "other",
]

# Safety budget for agent-like workloads
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
MAX_TOKENS_PER_RUN = int(os.getenv("MAX_TOKENS_PER_RUN", "50000"))
MAX_COST_USD = float(os.getenv("MAX_COST_USD", "1.0"))

# Cloud fallback order (only used if key + model are present)
CLOUD_FALLBACK_ORDER = [
    "GROQ",
    "OPENROUTER",
    "MISTRAL",
    "POLLINATIONS",
]

DEFAULT_CLOUD_MODELS = {
    "GROQ": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    "OPENROUTER": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
    "MISTRAL": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
    "POLLINATIONS": os.getenv("POLLINATIONS_MODEL", "openai-fast"),
    "DEEPSEEK": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "OPENAI": os.getenv("OPENAI_MODEL", ""),
}

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODELS = _parse_env_list("GROQ_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b,qwen/qwen3.8-27b")
GROQ_API_KEYS = _parse_env_list("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODELS = _parse_env_list(
    "OPENROUTER_MODELS",
    "openrouter/free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free,xingchen-agi/xing4.0-29b-a4b:free,cohere/north-mini-code:free",
)
OPENROUTER_API_KEYS = _parse_env_list("OPENROUTER_API_KEYS", os.getenv("OPENROUTER_API_KEY", ""))
OPENROUTER_BASE_URLS = _parse_env_list("OPENROUTER_BASE_URLS", OPENROUTER_BASE_URL)

MISTRAL_MODELS = _parse_env_list("MISTRAL_MODELS", "mistral-small-latest,codestral-latest")
MISTRAL_API_KEYS = _parse_env_list("MISTRAL_API_KEYS", os.getenv("MISTRAL_API_KEY", ""))

POLLINATIONS_BASE_URL = "https://text.pollinations.ai/openai"
POLLINATIONS_MODELS = ["openai-fast"]


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
