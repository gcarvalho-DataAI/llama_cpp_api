from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_int(name: str, default: int) -> int:
    return int(_get_env(name, str(default)))


def _get_float(name: str, default: float) -> float:
    return float(_get_env(name, str(default)))


def _get_csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    llama_cpp_base_url: str
    fallback_openai_api_key: str
    openai_api_keys: list[str]
    cors_allowed_origins: list[str]
    connect_timeout_s: float
    timeout_chat_s: float
    timeout_embeddings_s: float
    timeout_completions_s: float
    timeout_models_s: float
    max_retries: int
    retry_backoff_s: float
    rate_limit_rpm: int
    log_level: str


load_dotenv()

settings = Settings(
    llama_cpp_base_url=_get_env("LLAMA_CPP_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
    fallback_openai_api_key=_get_env("OPENAI_API_KEY", ""),
    openai_api_keys=_get_csv("OPENAI_API_KEYS"),
    cors_allowed_origins=_get_csv("CORS_ALLOWED_ORIGINS"),
    connect_timeout_s=_get_float("CONNECT_TIMEOUT_S", 5.0),
    timeout_chat_s=_get_float("TIMEOUT_CHAT_S", 120.0),
    timeout_embeddings_s=_get_float("TIMEOUT_EMBEDDINGS_S", 60.0),
    timeout_completions_s=_get_float("TIMEOUT_COMPLETIONS_S", 120.0),
    timeout_models_s=_get_float("TIMEOUT_MODELS_S", 10.0),
    max_retries=_get_int("MAX_RETRIES", 2),
    retry_backoff_s=_get_float("RETRY_BACKOFF_S", 0.35),
    rate_limit_rpm=_get_int("RATE_LIMIT_RPM", 120),
    log_level=_get_env("LOG_LEVEL", "info"),
)
