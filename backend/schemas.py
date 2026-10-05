"""Contrato HTTP entre el frontend (Angular) y el backend.

Los nombres de campo coinciden con las columnas del dataset procesado
(`recipe_id`, `total_time_min`, `country`...). Los valores de
`difficulty` y `category` se derivan de las columnas del modelo que ya
son los que usa el frontend. Un campo que el CSV no tiene para una receta
viaja como `null`; nunca se rellena con texto inventado.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Difficulty = Literal["facil", "intermedio", "reto"]
MealCategory = Literal["desayuno", "comida", "cena", "postre", "bebida"]


class RecommendationRequest(BaseModel):
    """Preferencias de "Sorpréndeme"."""

    model_config = ConfigDict(extra="forbid")

    tags: list[str] = Field(default_factory=list, max_length=16, description="Etiquetas exactas del dataset.")
    difficulty: Difficulty | None = Field(None, description="'Nivel de experiencia'.")
    max_time: int | None = Field(None, ge=1, le=720, description="Minutos disponibles.")
    countries: list[str] = Field(default_factory=list, max_length=40, description="Vacío = cualquier país.")
    exclude_ids: list[int] = Field(default_factory=list, max_length=5000, description="recipe_id a omitir.")
    top_n: int = Field(5, ge=1, le=50)


class IngredientsRequest(BaseModel):
    """Ingredientes de "Con lo que tengo"."""

    model_config = ConfigDict(extra="forbid")

    ingredients: list[str] = Field(min_length=1, max_length=50)
    exclude_ids: list[int] = Field(default_factory=list, max_length=5000)
    top_n: int = Field(5, ge=1, le=50)
    offset: int = Field(0, ge=0, le=1000, description="Cuántos resultados saltar (para 'buscar más').")
    fewest_extras: bool = Field(False, description="Ordena primero por menos ingredientes extra.")


class RecipeSummary(BaseModel):
    """Lo necesario para pintar una tarjeta."""

    recipe_id: int
    name: str
    ingredients: list[str]
    difficulty: Difficulty | None
    total_time_min: int | None
    servings: int | None
    country: str | None
    category: MealCategory | None
    meal_type: str | None
    source: str | None
    source_url: str | None


class RecommendationItem(RecipeSummary):
    similarity: float = Field(description="Similitud coseno TF-IDF.")
    score: float = Field(description="Similitud TF-IDF por la que se ordena.")
    matched_ingredients: list[str] | None = Field(
        None, description="Ingredientes del usuario que la receta usa (solo en 'Con lo que tengo')."
    )
    extra_ingredients: int | None = Field(None, description="Ingredientes de la receta que el usuario no tiene.")


class RecommendationMeta(BaseModel):
    candidates: int = Field(description="Recetas que pasaron los filtros antes del Top-N.")
    query_text: str | None
    applied_max_time: int | None
    relaxed: list[str] = Field(default_factory=list, description="Filtros blandos que se relajaron.")
    has_more: bool = Field(False, description="Hay más resultados después de esta página.")
    ingredients_total: int | None = Field(None, description="Ingredientes distintos que escribió el usuario.")
    best_match_count: int | None = Field(None, description="Máximo de esos ingredientes que usa una receta.")


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationItem]
    meta: RecommendationMeta


class MetadataResponse(BaseModel):
    tags: list[str]
    countries: list[str]


class RecipeResponse(RecipeSummary):
    """Receta completa (GET /recipes/{recipe_id})."""

    instructions: list[str]
    difficulty_source: str | None = Field(description="Valor original de `difficulty` en el CSV.")
    prep_time_min: int | None
    cook_time_min: int | None
    category_tags: list[str]
    diet_tags: list[str]
    description: str | None
    num_comments: int | None


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "bot"]
    text: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    """Pregunta al asistente + contexto de lo que el usuario ve en pantalla."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=40, description="Turnos previos, en orden.")
    recipe_id: int | None = Field(None, ge=1, description="Receta abierta (detalle), si la hay.")
    visible_recipe_ids: list[int] = Field(
        default_factory=list, max_length=12, description="Recetas mostradas en la lista actual."
    )
    allergies: list[Annotated[str, Field(max_length=60)]] = Field(
        default_factory=list, max_length=20, description="Alergias/restricciones activas del usuario (etiquetas)."
    )
    current_step: int | None = Field(None, ge=1, le=200, description="Paso en el que va el usuario, si la UI lo sabe.")


class ChatResponse(BaseModel):
    reply: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ErrorResponse(BaseModel):
    detail: str
