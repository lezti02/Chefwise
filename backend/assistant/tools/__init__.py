"""Herramientas de ChefWise.

Activas: escalado, conversión, sustitución, seguridad alimentaria, contexto de
paso, búsqueda de recetas y despensa (comparación con lo que dice el usuario).

No registradas (falta infraestructura en la app, ver README):
- nutrition_info: el dataset no tiene valores nutricionales.
- recipe_timer: la app no tiene temporizadores.
- búsqueda web: no hace falta para las preguntas de cocina actuales.
"""

from __future__ import annotations

from . import conversion, food_safety, scaling, substitution
from .base import Tool, ToolCallRecord, ToolContext, ToolError, ToolRegistry
from .recipe_tools import PANTRY_TOOL, SEARCH_TOOL, STEP_TOOL


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in (
        scaling.TOOL,
        conversion.TOOL,
        substitution.TOOL,
        food_safety.TOOL,
        STEP_TOOL,
        SEARCH_TOOL,
        PANTRY_TOOL,
    ):
        registry.register(tool)
    return registry


__all__ = ["Tool", "ToolCallRecord", "ToolContext", "ToolError", "ToolRegistry", "default_registry"]
