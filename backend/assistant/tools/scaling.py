"""calculate_recipe_scaling: cantidades para otro número de porciones."""

from __future__ import annotations

from pydantic import Field

from ..ingredients import contains_term, parse_ingredient
from ..units import format_amount
from .base import Tool, ToolContext, ToolError, ToolInput, ToolOutput

# Ingredientes que no escalan de forma lineal -> advertencia específica.
_SENSITIVE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("huevo", "yema", "clara"),
     "Huevos: no se pueden partir con precisión; redondea al entero más cercano o bate y mide la mitad (un huevo pesa ~50 g sin cáscara)."),
    (("levadura",),
     "Levadura: al aumentar mucho la masa, usa algo menos que lo proporcional y vigila el levado; el tiempo de fermentación cambia poco."),
    (("gelatina", "grenetina", "agar"),
     "Gelatina/grenetina: escala con exactitud (mejor por peso) para que cuaje igual."),
    (("sal",),
     "Sal: añade primero ~80 % de lo calculado y ajusta al probar."),
    (("pimienta", "comino", "canela", "clavo", "nuez moscada", "pimenton", "paprika", "curry", "chile en polvo",
      "chile seco", "oregano", "especia", "cayena", "azafran"),
     "Especias y chiles: no siempre escalan lineal; añade ~75 % y ajusta al gusto."),
    (("maicena", "fecula", "almidon", "harina de maiz", "espesante"),
     "Espesantes: la consistencia final puede variar; añádelos poco a poco."),
    (("polvo para hornear", "royal", "bicarbonato"),
     "Polvo para hornear/bicarbonato: mide con precisión; en cantidades grandes conviene hornear en tandas."),
)


class IngredientIn(ToolInput):
    name: str = Field(min_length=1, max_length=200)
    amount: float | None = Field(None, ge=0, description="Cantidad numérica; null si la receta no la indica.")
    unit: str | None = Field(None, max_length=40)
    optional: bool = False


class ScalingInput(ToolInput):
    servings_target: float = Field(gt=0, le=200, description="Porciones deseadas.")
    recipe_id: int | None = Field(
        None, ge=1, description="Receta a escalar; si se omite se usa la receta abierta y sus ingredientes reales."
    )
    servings_original: float | None = Field(
        None, gt=0, le=200, description="Porciones de la receta original; si se omite se usa el dato de la receta."
    )
    ingredients: list[IngredientIn] | None = Field(
        None, max_length=80, description="Solo si se quieren escalar ingredientes distintos a los de la receta."
    )


class ScaledIngredient(ToolOutput):
    name: str
    original_text: str | None = None
    original_amount: float | None
    amount: float | None
    amount_max: float | None = None
    amount_display: str | None
    unit: str | None
    optional: bool
    scaled: bool
    note: str | None = None


class ScalingOutput(ToolOutput):
    recipe_id: int | None
    servings_original: float
    servings_target: float
    scaling_factor: float
    scaled_ingredients: list[ScaledIngredient]
    warnings: list[str]


def _scale_one(name: str, text: str | None, amount: float | None, unit: str | None, optional: bool,
               factor: float, amount_max: float | None = None) -> ScaledIngredient:
    if amount is None:
        return ScaledIngredient(
            name=name, original_text=text, original_amount=None, amount=None, amount_display=None, unit=unit,
            optional=optional, scaled=False,
            note="Sin cantidad numérica en la receta: no se escaló (ajústalo al gusto).",
        )
    value = amount * factor
    rounded, display = format_amount(value, unit)
    note = None
    if any(contains_term(name, k) for k in ("huevo", "yema", "clara")) and unit in (None, "pieza", "piezas"):
        whole = max(1, round(value))
        if abs(whole - value) > 0.01:
            note = f"Cálculo exacto: {value:.2f}; en la práctica usa {whole}."
        rounded, display = float(whole), str(whole)
    rounded_max = None
    if amount_max is not None:
        rounded_max, display_max = format_amount(amount_max * factor, unit)
        display = f"{display} a {display_max}"
    return ScaledIngredient(
        name=name, original_text=text, original_amount=amount, amount=rounded, amount_max=rounded_max,
        amount_display=display, unit=unit, optional=optional, scaled=True, note=note,
    )


def run(inp: ScalingInput, ctx: ToolContext) -> ScalingOutput:
    recipe = None
    if inp.ingredients is None or inp.servings_original is None:
        recipe = ctx.recipe(inp.recipe_id)

    original = inp.servings_original or (recipe or {}).get("servings")
    if not original:
        raise ToolError(
            "missing_servings",
            "La receta no indica para cuántas porciones es; pregunta al usuario cuántas porciones rinde la original.",
        )
    factor = inp.servings_target / original

    items: list[ScaledIngredient] = []
    if inp.ingredients is not None:
        items = [_scale_one(i.name, None, i.amount, i.unit, i.optional, factor) for i in inp.ingredients]
    else:
        lines = (recipe or {}).get("ingredients") or []
        if not lines:
            raise ToolError("missing_ingredients", "La receta no tiene ingredientes registrados.")
        for line in lines:
            p = parse_ingredient(line)
            items.append(_scale_one(p.name, p.text, p.amount, p.unit, p.optional, factor, p.amount_max))

    warnings: list[str] = []
    names = " | ".join(i.name for i in items)
    for keywords, warning in _SENSITIVE:
        if any(contains_term(names, k) for k in keywords):
            warnings.append(warning)
    if factor >= 1.5 or factor <= 0.67:
        warnings.append(
            "Tiempos y recipientes: con más o menos cantidad cambia el tamaño de olla/molde y los tiempos de cocción; vigila el punto."
        )
    if any(not i.scaled for i in items):
        warnings.append("Algunos ingredientes no tienen cantidad en la receta y no se escalaron.")

    return ScalingOutput(
        recipe_id=(recipe or {}).get("recipe_id"),
        servings_original=original,
        servings_target=inp.servings_target,
        scaling_factor=round(factor, 4),
        scaled_ingredients=items,
        warnings=warnings,
    )


TOOL = Tool(
    name="calculate_recipe_scaling",
    description=(
        "Calcula las cantidades de los ingredientes para otro número de porciones. Sin `ingredients` usa los "
        "ingredientes y porciones reales de la receta abierta. Devuelve cantidades redondeadas y advertencias."
    ),
    input_model=ScalingInput,
    output_model=ScalingOutput,
    handler=run,
    status_label="Calculando cantidades…",
)
