"""Proveedores de IA. Para añadir Claude u OpenAI: una clase con `run()` (ver `base.ChatProvider`)
que traduzca `ToolRegistry.declarations()` a su formato de tools, registrada en `PROVIDERS`."""

from __future__ import annotations

import logging

from ...settings import ChatSettings
from .base import ChatProvider, ChatUnavailableError, ProviderResult, Turn
from .gemini import GeminiProvider

logger = logging.getLogger("chefwise.assistant")

PROVIDERS = {"gemini": GeminiProvider}


def build_provider(settings: ChatSettings) -> ChatProvider | None:
    """None si falta la API key: el resto de la API funciona sin el chat."""
    try:
        provider_cls = PROVIDERS[settings.provider]
    except KeyError:
        raise ValueError(
            f"CHEFWISE_LLM_PROVIDER='{settings.provider}' no es válido. Opciones: {', '.join(PROVIDERS)}"
        ) from None
    if not settings.api_key:
        logger.warning("Chat deshabilitado: falta la API key del proveedor '%s'.", settings.provider)
        return None
    return provider_cls(api_key=settings.api_key, model=settings.model, timeout=settings.timeout)


__all__ = ["ChatProvider", "ChatUnavailableError", "ProviderResult", "Turn", "build_provider", "PROVIDERS"]
