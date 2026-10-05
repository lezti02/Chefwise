"""Infraestructura común de las herramientas (tools) de ChefWise.

Cada herramienta declara: nombre, descripción, modelo Pydantic de entrada (de
él sale el JSON Schema que ve la IA), modelo de salida y un handler. El
registro valida la entrada, valida la salida, mide la duración y convierte
cualquier fallo en un error estructurado: el modelo nunca recibe un resultado
inventado ni un stack trace.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from ..recipes import RecipeRepository

logger = logging.getLogger("chefwise.assistant.tools")

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolError(Exception):
    """Error esperado (dato faltante, unidad desconocida...). El mensaje se le pasa a la IA."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ToolContext:
    """Lo que una herramienta puede usar además de sus argumentos."""

    recipes: RecipeRepository
    current_recipe_id: int | None = None
    allergies: tuple[str, ...] = ()

    def recipe_id_or_current(self, recipe_id: int | None) -> int:
        rid = recipe_id if recipe_id is not None else self.current_recipe_id
        if rid is None:
            raise ToolError("no_recipe", "No hay una receta abierta; indica recipe_id o pide al usuario que abra una receta.")
        return rid

    def recipe(self, recipe_id: int | None) -> dict[str, Any]:
        rid = self.recipe_id_or_current(recipe_id)
        recipe = self.recipes.get(rid)
        if recipe is None:
            raise ToolError("recipe_not_found", f"No existe la receta con recipe_id={rid}.")
        return recipe


@dataclass(frozen=True)
class Tool(Generic[In, Out]):
    name: str
    description: str
    input_model: type[In]
    output_model: type[Out]
    handler: Callable[[In, ToolContext], Out]
    status_label: str  # texto amable para la UI ("Calculando cantidades…")

    def json_schema(self) -> dict[str, Any]:
        return _strip_titles(self.input_model.model_json_schema())


@dataclass
class ToolCallRecord:
    name: str
    ok: bool
    duration_ms: float
    error_code: str | None = None


@dataclass
class ToolRegistry:
    tools: dict[str, Tool[Any, Any]] = field(default_factory=dict)

    def register(self, tool: Tool[Any, Any]) -> None:
        if tool.name in self.tools:
            raise ValueError(f"Herramienta duplicada: {tool.name}")
        self.tools[tool.name] = tool

    def declarations(self) -> list[dict[str, Any]]:
        """Formato neutral: cada proveedor lo adapta (Gemini, Claude y OpenAI aceptan JSON Schema)."""
        return [
            {"name": t.name, "description": t.description, "parameters": t.json_schema()}
            for t in self.tools.values()
        ]

    def execute(self, name: str, args: dict[str, Any] | None, ctx: ToolContext) -> tuple[dict[str, Any], ToolCallRecord]:
        """Ejecuta y devuelve `{"ok": True, "result": ...}` o `{"ok": False, "error": {...}}`."""
        start = time.perf_counter()
        tool = self.tools.get(name)
        if tool is None:
            return self._fail(name, start, "unknown_tool", f"La herramienta '{name}' no existe.")
        try:
            parsed = tool.input_model.model_validate(args or {})
        except ValidationError as exc:
            return self._fail(name, start, "invalid_input", _validation_message(exc))
        try:
            result = tool.handler(parsed, ctx)
            output = tool.output_model.model_validate(result.model_dump() if isinstance(result, BaseModel) else result)
        except ToolError as exc:
            return self._fail(name, start, exc.code, exc.message)
        except ValidationError:
            logger.exception("Salida inválida de la herramienta %s", name)
            return self._fail(name, start, "invalid_output", "La herramienta produjo un resultado inválido; no lo uses.")
        except Exception:
            logger.exception("Fallo inesperado en la herramienta %s", name)
            return self._fail(name, start, "internal_error", "La herramienta falló; no inventes su resultado.")
        record = ToolCallRecord(name, True, _ms(start))
        logger.info("tool=%s ok duration_ms=%.1f", name, record.duration_ms)
        return {"ok": True, "result": output.model_dump()}, record

    @staticmethod
    def _fail(name: str, start: float, code: str, message: str) -> tuple[dict[str, Any], ToolCallRecord]:
        record = ToolCallRecord(name, False, _ms(start), code)
        logger.info("tool=%s error=%s duration_ms=%.1f", name, code, record.duration_ms)
        return {"ok": False, "error": {"code": code, "message": message}}, record


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def _validation_message(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors(include_url=False, include_input=False):
        loc = ".".join(str(p) for p in err["loc"]) or "entrada"
        parts.append(f"{loc}: {err['msg']}")
    return "Entrada inválida: " + "; ".join(parts[:5])


def _strip_titles(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_strip_titles(v) for v in schema]
    return schema
