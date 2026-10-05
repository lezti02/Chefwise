"""food_safety: temperaturas internas seguras, conservación, recalentado y descongelación."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..ingredients import contains_term
from ..knowledge import food_safety as data
from .base import Tool, ToolContext, ToolInput, ToolOutput


class FoodSafetyInput(ToolInput):
    food: str = Field(min_length=1, max_length=120, description="Alimento (p. ej. 'pechuga de pollo', 'carne molida', 'sobras').")
    preparation_method: str | None = Field(None, max_length=120, description="p. ej. 'molido', 'relleno', 'marinado'.")
    cooking_method: str | None = Field(None, max_length=120, description="p. ej. 'horno', 'parrilla', 'freír', 'crudo'.")
    target_temperature: float | None = Field(None, ge=-50, le=400, description="Temperatura que el usuario piensa usar o midió.")
    target_temperature_unit: Literal["C", "F"] = "C"
    storage_question: str | None = Field(
        None, max_length=200, description="Duda de conservación/recalentado/descongelación, si la hay."
    )


class SafeTemperature(ToolOutput):
    celsius: int
    fahrenheit: int
    rest_minutes: int | None = None


class FoodSafetyOutput(ToolOutput):
    found: bool
    food_category: str | None
    safe_temperature: SafeTemperature | None
    measurement_guidance: str
    cooking_guidance: str | None
    storage_guidance: str
    reheating_guidance: str
    thawing_guidance: str
    warnings: list[str]
    source: str


def _match(food: str) -> data.SafetyEntry | None:
    best: tuple[int, data.SafetyEntry] | None = None
    for entry in data.ENTRIES:
        for key in entry.keys:
            if contains_term(food, key) and (best is None or len(key) > best[0]):
                best = (len(key), entry)
    return best[1] if best else None


def run(inp: FoodSafetyInput, _: ToolContext) -> FoodSafetyOutput:
    text = " ".join(filter(None, [inp.food, inp.preparation_method]))
    entry = _match(text)
    ground = any(contains_term(text, k) for k in ("molido", "molida"))
    if entry and ground and entry.id in ("carne_entera", "aves"):
        target = "carne_molida" if entry.id == "carne_entera" else "aves_molidas"
        entry = next(e for e in data.ENTRIES if e.id == target)

    warnings: list[str] = []
    safe = None
    if entry and entry.min_temp_c is not None and entry.min_temp_f is not None:
        safe = SafeTemperature(celsius=entry.min_temp_c, fahrenheit=entry.min_temp_f, rest_minutes=entry.rest_minutes)
        if inp.target_temperature is not None:
            target_c = inp.target_temperature if inp.target_temperature_unit == "C" else (inp.target_temperature - 32) * 5 / 9
            if target_c < entry.min_temp_c:
                warnings.append(
                    f"{inp.target_temperature:g} °{inp.target_temperature_unit} está por debajo de la temperatura interna "
                    f"mínima segura ({entry.min_temp_c} °C / {entry.min_temp_f} °F) para {entry.label}."
                )
    if entry:
        warnings.extend(entry.extra_warnings)
    if inp.cooking_method and contains_term(inp.cooking_method, "crudo") and entry and entry.min_temp_c:
        warnings.append("Consumirlo crudo o poco cocido aumenta el riesgo de enfermedades transmitidas por alimentos.")
    if not entry:
        warnings.append(
            "No hay datos específicos de temperatura para este alimento: da solo las reglas generales y no inventes cifras."
        )

    storage = data.STORAGE_GENERAL
    if entry and entry.fridge_raw:
        storage = f"{entry.label.capitalize()} crudo: {entry.fridge_raw}. {storage}"
    return FoodSafetyOutput(
        found=entry is not None,
        food_category=entry.label if entry else None,
        safe_temperature=safe,
        measurement_guidance=data.MEASUREMENT_GENERAL,
        cooking_guidance=entry.cooking_guidance if entry else None,
        storage_guidance=storage,
        reheating_guidance=data.REHEATING_GENERAL,
        thawing_guidance=data.THAWING_GENERAL,
        warnings=warnings,
        source=data.SOURCE,
    )


TOOL = Tool(
    name="food_safety",
    description=(
        "Datos oficiales de seguridad alimentaria (USDA): temperatura interna mínima segura de carnes, aves, "
        "pescado, mariscos, huevo y sobras; cómo medirla; conservación, recalentado y descongelación. Si se pasa "
        "target_temperature, avisa si es insegura."
    ),
    input_model=FoodSafetyInput,
    output_model=FoodSafetyOutput,
    handler=run,
    status_label="Consultando seguridad alimentaria…",
)
