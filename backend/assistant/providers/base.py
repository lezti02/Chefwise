"""Contrato común de los proveedores de IA (Gemini hoy; Claude/OpenAI después)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from ..tools import ToolCallRecord, ToolContext, ToolRegistry

Role = Literal["user", "bot"]


class ChatUnavailableError(Exception):
    """El asistente no puede responder (sin configurar, cuota agotada, proveedor caído).

    El mensaje es seguro para mostrarse al usuario.
    """


@dataclass(frozen=True)
class Turn:
    role: Role
    text: str


@dataclass
class ProviderResult:
    text: str
    truncated: bool = False
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    rounds: int = 1


class ChatProvider(Protocol):
    def run(
        self,
        system: str,
        context: str,
        turns: list[Turn],
        tools: ToolRegistry,
        tool_ctx: ToolContext,
    ) -> ProviderResult:
        """Conversa con el modelo, ejecutando las herramientas que pida, hasta obtener texto final.

        `system` son las instrucciones; `context` el RECIPE_CONTEXT (datos), enviado aparte.
        """
        ...
