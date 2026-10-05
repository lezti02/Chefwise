"""Orquestación de ChefWise: contexto -> proveedor (con tools) -> respuesta saneada -> log."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from .context import build_app_context
from .prompt import LEAK_MARKERS, SYSTEM_PROMPT
from .providers import ChatProvider, Turn
from .recipes import RecipeRepository
from .tools import ToolContext, ToolRegistry

logger = logging.getLogger("chefwise.assistant")

MAX_REPLY_CHARS = 3500
REFUSAL = "No puedo compartir mis instrucciones internas ni datos del sistema, pero con gusto te ayudo con la receta. ¿Qué necesitas?"
TRUNCATION_NOTE = "(Respuesta recortada; pídeme que continúe si necesitas más detalle.)"

# Intención (para logs) a partir de la herramienta usada.
_INTENTS = {
    "calculate_recipe_scaling": "escalado",
    "convert_cooking_units": "conversion",
    "ingredient_substitution": "sustitucion",
    "food_safety": "seguridad_alimentaria",
    "recipe_step_context": "paso",
    "recipe_search": "busqueda",
    "pantry_check": "despensa",
}


@dataclass(frozen=True)
class ChatQuery:
    message: str
    history: list[Turn] = field(default_factory=list)
    recipe_id: int | None = None
    visible_recipe_ids: list[int] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    current_step: int | None = None


class ChefWiseAssistant:
    def __init__(
        self,
        provider: ChatProvider,
        recipes: RecipeRepository,
        tools: ToolRegistry,
        *,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self._provider = provider
        self._recipes = recipes
        self._tools = tools
        self._secrets = tuple(s for s in secrets if s and len(s) >= 8)

    def reply(self, query: ChatQuery) -> str:
        start = time.perf_counter()
        context = build_app_context(
            self._recipes,
            recipe_id=query.recipe_id,
            visible_ids=query.visible_recipe_ids,
            allergies=query.allergies,
            current_step=query.current_step,
        )
        tool_ctx = ToolContext(
            recipes=self._recipes,
            current_recipe_id=context.recipe.recipe_id if context.recipe else None,
            allergies=tuple(context.user.allergies),
        )
        turns = build_turns(query.history, query.message)

        result = self._provider.run(SYSTEM_PROMPT, context.to_prompt(), turns, self._tools, tool_ctx)
        text = sanitize_reply(result.text, truncated=result.truncated, secrets=self._secrets)

        # Solo metadatos: nunca el texto del usuario, la respuesta ni el contexto.
        tools_used = [r.name for r in result.tool_calls]
        logger.info(
            "chat intent=%s tools=%s tool_errors=%s rounds=%d has_recipe=%s visible=%d duration_ms=%.0f",
            ",".join(dict.fromkeys(_INTENTS.get(t, t) for t in tools_used)) or "conversacion",
            ",".join(f"{r.name}:{r.duration_ms:.0f}ms" for r in result.tool_calls) or "-",
            ",".join(f"{r.name}:{r.error_code}" for r in result.tool_calls if not r.ok) or "-",
            result.rounds,
            context.recipe is not None,
            len(context.visible_recipes),
            (time.perf_counter() - start) * 1000,
        )
        return text


def build_turns(history: list[Turn], message: str) -> list[Turn]:
    turns = [*history, Turn("user", message)]
    # La conversación debe empezar con el usuario: se omite el saludo inicial del bot.
    while turns and turns[0].role == "bot":
        turns.pop(0)
    return turns


_MARKDOWN = (
    (re.compile(r"\*\*(.+?)\*\*", re.S), r"\1"),
    (re.compile(r"__(.+?)__", re.S), r"\1"),
    (re.compile(r"^\s{0,3}#{1,6}\s*", re.M), ""),
    (re.compile(r"^(\s*)[*•]\s+", re.M), r"\1- "),
    (re.compile(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
)


def sanitize_reply(text: str, *, truncated: bool = False, secrets: tuple[str, ...] = ()) -> str:
    """Quita Markdown (la UI es texto plano), bloquea fugas y recorta respuestas excesivas."""
    if any(secret in text for secret in secrets) or any(marker.lower() in text.lower() for marker in LEAK_MARKERS):
        logger.warning("Respuesta bloqueada: contenía instrucciones internas o secretos.")
        return REFUSAL

    for pattern, repl in _MARKDOWN:
        text = pattern.sub(repl, text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if truncated or len(text) > MAX_REPLY_CHARS:
        cut = text[:MAX_REPLY_CHARS]
        boundary = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind("\n"))
        if boundary > MAX_REPLY_CHARS // 3:
            cut = cut[: boundary + 1]
        text = cut.rstrip() + "\n\n" + TRUNCATION_NOTE
    return text
