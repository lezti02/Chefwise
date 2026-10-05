"""ingredient_substitution: sustituciones según la función del ingrediente y las restricciones."""

from __future__ import annotations

from pydantic import Field

from src.text_utils import normalize_text

from ..allergens import ALLERGENS, to_restriction
from ..ingredients import contains_term
from ..knowledge.substitutions import SUBSTITUTIONS, SubEntry, SubOption
from ..units import format_amount, normalize_unit
from .base import Tool, ToolContext, ToolInput, ToolOutput

_ALLERGEN_LABELS = {r.id: r.label for r in ALLERGENS}


class SubstitutionInput(ToolInput):
    ingredient: str = Field(min_length=1, max_length=120, description="Ingrediente a sustituir.")
    amount: float | None = Field(None, ge=0, description="Cantidad del ingrediente original, si se conoce.")
    unit: str | None = Field(None, max_length=40)
    recipe_context: str | None = Field(
        None, max_length=300, description="Uso en la receta (p. ej. 'capeado de pescado', 'pastel', 'salsa')."
    )
    dietary_restrictions: list[str] = Field(default_factory=list, max_length=10, description="p. ej. vegano, sin gluten.")
    allergies: list[str] = Field(default_factory=list, max_length=10)
    desired_properties: list[str] = Field(default_factory=list, max_length=10, description="p. ej. crujiente, sin alcohol.")


class Substitution(ToolOutput):
    substitute: str
    ratio: str
    amount: str | None = None
    instructions: str
    flavor_changes: str
    texture_changes: str
    contains_allergens: list[str]


class SubstitutionOutput(ToolOutput):
    found: bool
    ingredient: str
    function: str | None
    substitutions: list[Substitution]
    excluded_by_restrictions: list[str]
    ratio: str | None = Field(None, description="Proporción de la opción recomendada (la primera).")
    instructions: str | None = None
    flavor_changes: str | None = None
    texture_changes: str | None = None
    warnings: list[str]


def _find_entry(ingredient: str) -> SubEntry | None:
    norm = normalize_text(ingredient)
    best: tuple[int, SubEntry] | None = None
    for entry in SUBSTITUTIONS:
        for key in entry.keys:
            if contains_term(norm, key) and (best is None or len(key) > best[0]):
                best = (len(key), entry)
    return best[1] if best else None


def _blocked(option: SubOption, restrictions: list[str]) -> bool:
    for term in restrictions:
        key = normalize_text(term).strip()
        if key == "vegano" and not option.vegan:
            return True
        if key == "sin alcohol" and option.alcohol:
            return True
        restriction = to_restriction(term)
        if any(rule.id in option.allergens for rule in restriction.rules):
            return True
        if any(contains_term(option.substitute, k) for k in restriction.extra_keywords):
            return True
    return False


def _score(option: SubOption, wanted: str) -> int:
    return sum(1 for use in option.good_for if contains_term(wanted, use))


def run(inp: SubstitutionInput, ctx: ToolContext) -> SubstitutionOutput:
    warnings: list[str] = []
    recipe = ctx.recipes.get(ctx.current_recipe_id) if ctx.current_recipe_id else None
    if recipe and not any(contains_term(line, inp.ingredient) for line in recipe.get("ingredients") or []):
        warnings.append(f"'{inp.ingredient}' no aparece en los ingredientes de la receta abierta.")

    entry = _find_entry(inp.ingredient)
    if entry is None:
        return SubstitutionOutput(
            found=False, ingredient=inp.ingredient, function=None, substitutions=[], excluded_by_restrictions=[],
            warnings=warnings + [
                "No hay datos de este ingrediente en la base de sustituciones: si propones algo, preséntalo como "
                "conocimiento culinario general y explica la función del ingrediente."
            ],
        )

    restrictions = [*inp.dietary_restrictions, *inp.allergies, *ctx.allergies]
    wanted = " ".join(filter(None, [inp.recipe_context, (recipe or {}).get("name"), *inp.desired_properties, *restrictions]))
    allowed: list[SubOption] = []
    excluded: list[str] = []
    for option in entry.options:
        (excluded if _blocked(option, restrictions) else allowed).append(option)
    allowed.sort(key=lambda o: _score(o, wanted), reverse=True)

    unit_key = normalize_unit(inp.unit) or inp.unit
    subs = []
    for option in allowed:
        amount = None
        if inp.amount is not None and option.ratio_factor is not None:
            _, display = format_amount(inp.amount * option.ratio_factor, unit_key)
            amount = f"{display} {inp.unit or ''}".strip()
        subs.append(
            Substitution(
                substitute=option.substitute, ratio=option.ratio, amount=amount, instructions=option.instructions,
                flavor_changes=option.flavor_changes, texture_changes=option.texture_changes,
                contains_allergens=[_ALLERGEN_LABELS[a] for a in option.allergens],
            )
        )

    warnings.extend(entry.warnings)
    if not subs:
        warnings.append("Ninguna sustitución conocida es compatible con las restricciones indicadas.")
    if any(s.contains_allergens for s in subs):
        warnings.append("Algunas opciones contienen alérgenos (ver contains_allergens).")
    if restrictions:
        warnings.append("Con alergias graves, revisa las etiquetas: los productos pueden tener trazas o contaminación cruzada.")
    first = subs[0] if subs else None
    return SubstitutionOutput(
        found=True, ingredient=entry.label, function=entry.function, substitutions=subs, excluded_by_restrictions=[o.substitute for o in excluded],
        ratio=first.ratio if first else None, instructions=first.instructions if first else None,
        flavor_changes=first.flavor_changes if first else None, texture_changes=first.texture_changes if first else None,
        warnings=warnings,
    )


TOOL = Tool(
    name="ingredient_substitution",
    description=(
        "Propone sustitutos de un ingrediente según su función culinaria, con proporción, instrucciones y cambios "
        "de sabor/textura. Filtra opciones incompatibles con alergias y dietas (las alergias del usuario se "
        "aplican automáticamente). found=false si el ingrediente no está en la base."
    ),
    input_model=SubstitutionInput,
    output_model=SubstitutionOutput,
    handler=run,
    status_label="Preparando sustitución…",
)
