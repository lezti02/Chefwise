"""Acceso a recetas para el asistente (adaptador sobre `src.recommender.Recommender`).

Las herramientas y el contexto dependen de este protocolo, no del recomendador:
así se pueden probar con recetas falsas y, si algún día hay base de datos, solo
cambia esta capa.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.exceptions import RecipeNotFoundError
from src.recommender import Recommender


class RecipeRepository(Protocol):
    def get(self, recipe_id: int) -> dict[str, Any] | None:
        """Receta completa (mismo formato que GET /recipes/{id}) o None si no existe."""

    def search(self, text: str, *, max_minutes: int | None, exclude_ids: tuple[int, ...], top_n: int) -> list[dict[str, Any]]:
        """Resúmenes ordenados por similitud con el texto."""


class RecommenderRepository:
    def __init__(self, recommender: Recommender) -> None:
        self._recommender = recommender

    def get(self, recipe_id: int) -> dict[str, Any] | None:
        try:
            return self._recommender.get_recipe(recipe_id)
        except RecipeNotFoundError:
            return None

    def search(self, text: str, *, max_minutes: int | None, exclude_ids: tuple[int, ...], top_n: int) -> list[dict[str, Any]]:
        result = self._recommender.recommend_by_ingredients(
            [text], exclude_ids=exclude_ids, top_n=top_n, max_minutes=max_minutes
        )
        return [item.summary for item in result.items]
