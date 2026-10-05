"""Configuración del backend (variables de entorno)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path = _ENV_FILE) -> None:
    """Carga `KEY=valor` de `.env` (raíz del proyecto) sin pisar variables ya definidas."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file()

# `ng serve` usa el puerto 4200 por defecto. Se puede cambiar con una lista
# separada por comas, p. ej.: CHEFWISE_CORS_ORIGINS="http://localhost:4200,https://chefwise.example"
_DEFAULT_ORIGINS = "http://localhost:4200,http://127.0.0.1:4200"


def cors_origins() -> list[str]:
    raw = os.getenv("CHEFWISE_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


# Proveedor de IA del chat → (variable con la API key, modelo por defecto).
_LLM_DEFAULTS = {
    "gemini": ("GEMINI_API_KEY", "gemini-flash-lite-latest"),
}


@dataclass(frozen=True)
class ChatSettings:
    provider: str
    api_key: str | None
    model: str
    timeout: float


def chat_settings() -> ChatSettings:
    provider = os.getenv("CHEFWISE_LLM_PROVIDER", "gemini").strip().lower()
    key_var, default_model = _LLM_DEFAULTS.get(provider, ("", ""))
    return ChatSettings(
        provider=provider,
        api_key=os.getenv(key_var) or None if key_var else None,
        model=os.getenv("CHEFWISE_LLM_MODEL", default_model),
        timeout=float(os.getenv("CHEFWISE_LLM_TIMEOUT", "30")),
    )
