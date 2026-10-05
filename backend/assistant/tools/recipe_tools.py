"""Herramientas sobre los datos reales de recetas: paso actual, búsqueda y despensa."""

from __future__ import annotations

from pydantic import Field

from src.text_utils import normalize_text

from ..allergens import to_restriction
from ..context import extract_temperatures, extract_times
from ..ingredients import mentions, parse_ingredient
from .base import Tool, ToolContext, ToolError, ToolInput, ToolOutput

# ------------------------------------------------------------ recipe_step_context


class StepInput(ToolInput):
    step_number: int = Field(ge=1, le=200, description="Número de paso (empieza en 1).")
    recipe_id: int | None = Field(None, ge=1, description="Si se omite, la receta abierta.")


class StepOutput(ToolOutput):
    recipe_id: int
    total_steps: int
    step_number: int
    step: str
    ingredients: list[str] = Field(description="Renglones de la receta mencionados en el paso (detección por texto).")
    time: list[str] = Field(description="Tiempos escritos en el paso; vacío si no menciona ninguno.")
    temperature: list[str] = Field(description="Temperaturas escritas en el paso; vacío si no menciona ninguna.")
    previous_step: str | None
    next_step: str | None
    note: str


def run_step(inp: StepInput, ctx: ToolContext) -> StepOutput:
    recipe = ctx.recipe(inp.recipe_id)
    steps = recipe.get("instructions") or []
    if not steps:
        raise ToolError("no_steps", "La receta no tiene pasos registrados.")
    if inp.step_number > len(steps):
        raise ToolError("step_out_of_range", f"La receta solo tiene {len(steps)} pasos.")
    text = steps[inp.step_number - 1]
    norm = normalize_text(text)
    used = []
    for line in recipe.get("ingredients") or []:
        keywords = parse_ingredient(line).keywords()
        if keywords and any(mentions(norm, k) for k in keywords[:2]):
            used.append(line)
    return StepOutput(
        recipe_id=recipe["recipe_id"],
        total_steps=len(steps),
        step_number=inp.step_number,
        step=text,
        ingredients=used,
        time=extract_times(text),
        temperature=extract_temperatures(text),
        previous_step=steps[inp.step_number - 2] if inp.step_number > 1 else None,
        next_step=steps[inp.step_number] if inp.step_number < len(steps) else None,
        note="Tiempos y temperaturas son los escritos en el texto del paso; si no aparecen, la receta no los indica.",
    )


STEP_TOOL = Tool(
    name="recipe_step_context",
    description=(
        "Devuelve un paso concreto de la receta con los ingredientes que menciona, los tiempos y temperaturas "
        "escritos en él y los pasos anterior y siguiente."
    ),
    input_model=StepInput,
    output_model=StepOutput,
    handler=run_step,
    status_label="Revisando el paso…",
)

# ------------------------------------------------------------------ recipe_search


class SearchInput(ToolInput):
    query: str | None = Field(None, max_length=200, description="Qué busca el usuario (platillo, estilo, ocasión).")
    ingredients: list[str] = Field(default_factory=list, max_length=20)
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=10, description="p. ej. vegetariano, sin gluten, sin lácteos.")
    max_time: int | None = Field(None, ge=1, le=720, description="Minutos máximos.")
    servings: int | None = Field(None, ge=1, le=100, description="Porciones deseadas (se informan; se pueden escalar).")
    limit: int = Field(5, ge=1, le=8)


class SearchResult(ToolOutput):
    recipe_id: int
    name: str
    total_time_min: int | None
    servings: int | None
    difficulty: str | None
    country: str | None
    category: str | None


class SearchOutput(ToolOutput):
    results: list[SearchResult]
    excluded_by_restrictions: int
    note: str | None = None


def run_search(inp: SearchInput, ctx: ToolContext) -> SearchOutput:
    text = " ".join(filter(None, [inp.query, *inp.ingredients])).strip()
    if not text:
        raise ToolError("empty_query", "Indica qué buscar (query o ingredients).")
    restrictions = [to_restriction(r) for r in [*inp.dietary_restrictions, *ctx.allergies]]
    exclude = (ctx.current_recipe_id,) if ctx.current_recipe_id else ()
    candidates = ctx.recipes.search(text, max_minutes=inp.max_time, exclude_ids=exclude, top_n=50)

    results: list[SearchResult] = []
    excluded = 0
    for summary in candidates:
        lines = [summary["name"], *summary.get("ingredients", [])]
        if any(r.matches(line) for r in restrictions for line in lines):
            excluded += 1
            continue
        results.append(SearchResult(**{k: summary.get(k) for k in SearchResult.model_fields}))
        if len(results) >= inp.limit:
            break
    note = None
    if not results:
        note = "No se encontraron recetas en la app con esos criterios."
    elif inp.servings:
        note = "Las porciones son las de cada receta; se pueden escalar con calculate_recipe_scaling."
    return SearchOutput(results=results, excluded_by_restrictions=excluded, note=note)


SEARCH_TOOL = Tool(
    name="recipe_search",
    description=(
        "Busca recetas en el catálogo de la app (no en internet) por texto e ingredientes, con filtros de tiempo "
        "máximo y restricciones (las alergias del usuario se aplican siempre)."
    ),
    input_model=SearchInput,
    output_model=SearchOutput,
    handler=run_search,
    status_label="Buscando recetas…",
)

# -------------------------------------------------------------------- pantry_check

# Básicos que casi cualquier cocina tiene: se informan aparte en vez de contarlos como faltantes.
_BASICS = ("sal", "pimienta", "agua", "aceite")


class PantryInput(ToolInput):
    available_ingredients: list[str] = Field(min_length=1, max_length=50, description="Lo que el usuario dice tener.")
    recipe_id: int | None = Field(None, ge=1, description="Si se omite, la receta abierta.")


class PantryOutput(ToolOutput):
    recipe_id: int
    have: list[str]
    missing: list[str]
    missing_optional: list[str]
    basics_assumed: list[str]
    can_make: bool
    note: str


def run_pantry(inp: PantryInput, ctx: ToolContext) -> PantryOutput:
    recipe = ctx.recipe(inp.recipe_id)
    lines = recipe.get("ingredients") or []
    if not lines:
        raise ToolError("missing_ingredients", "La receta no tiene ingredientes registrados.")
    available = normalize_text(" | ".join(inp.available_ingredients))
    have, missing, missing_optional, basics = [], [], [], []
    for line in lines:
        parsed = parse_ingredient(line)
        keywords = parsed.keywords()
        if keywords and any(mentions(available, k) for k in keywords[:2]):
            have.append(line)
        elif any(mentions(normalize_text(parsed.name), b) for b in _BASICS) and len(keywords) <= 2:
            basics.append(line)
        elif parsed.optional:
            missing_optional.append(line)
        else:
            missing.append(line)
    return PantryOutput(
        recipe_id=recipe["recipe_id"],
        have=have,
        missing=missing,
        missing_optional=missing_optional,
        basics_assumed=basics,
        can_make=not missing,
        note=(
            "Comparación por texto entre lo que dijo el usuario y los ingredientes de la receta; confirma los "
            "dudosos. Para faltantes puedes usar ingredient_substitution."
        ),
    )


PANTRY_TOOL = Tool(
    name="pantry_check",
    description=(
        "Compara los ingredientes que el usuario dice tener con los de la receta: cuáles tiene, cuáles faltan "
        "(obligatorios u opcionales) y si puede prepararla."
    ),
    input_model=PantryInput,
    output_model=PantryOutput,
    handler=run_pantry,
    status_label="Revisando tus ingredientes…",
)
