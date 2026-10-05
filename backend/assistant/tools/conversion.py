"""convert_cooking_units: peso, volumen, temperatura y volumen<->peso con densidad."""

from __future__ import annotations

from pydantic import Field

from ..ingredients import contains_term
from ..units import UNITS, format_amount, normalize_unit, supported_units_text
from .base import Tool, ToolContext, ToolError, ToolInput, ToolOutput

# Densidades aproximadas (g/ml) a partir de pesos estándar por taza (236.6 ml):
# harina 125 g, azúcar 200 g, azúcar morena compacta 220 g, azúcar glas 120 g,
# mantequilla 227 g, aceite 218 g, miel 340 g, arroz crudo 185 g, avena 90 g,
# cacao 85 g, sal fina 288 g. Varían con la forma de medir: siempre son aproximadas.
DENSITIES: tuple[tuple[tuple[str, ...], str, float], ...] = (
    (("harina integral",), "harina integral", 0.55),
    (("harina", "flour"), "harina de trigo", 0.53),
    (("maicena", "fecula", "almidon"), "fécula de maíz", 0.54),
    (("azucar glas", "azucar glass", "azucar pulverizada", "azucar impalpable"), "azúcar glas", 0.51),
    (("azucar morena", "azucar mascabado", "piloncillo rallado"), "azúcar morena (compacta)", 0.93),
    (("azucar",), "azúcar blanca", 0.85),
    (("mantequilla", "margarina", "butter"), "mantequilla", 0.96),
    (("aceite",), "aceite", 0.92),
    (("miel", "jarabe", "maple"), "miel", 1.42),
    (("leche",), "leche", 1.03),
    (("crema", "nata"), "crema", 1.0),
    (("yogur", "yogurt"), "yogur", 1.03),
    (("agua", "caldo", "consome", "jugo", "zumo", "vinagre", "vino", "cerveza"), "líquido acuoso", 1.0),
    (("arroz",), "arroz crudo", 0.78),
    (("avena",), "avena en hojuelas", 0.38),
    (("cacao", "chocolate en polvo"), "cacao en polvo", 0.36),
    (("sal",), "sal fina", 1.22),
)


class ConversionInput(ToolInput):
    value: float = Field(description="Cantidad a convertir (negativa solo en temperaturas).")
    from_unit: str = Field(min_length=1, max_length=40, description="g, kg, oz, lb, ml, l, tsp, tbsp, cup, °C, °F o su nombre en español.")
    to_unit: str = Field(min_length=1, max_length=40)
    ingredient: str | None = Field(None, max_length=120, description="Necesario para convertir volumen <-> peso.")


class ConversionOutput(ToolOutput):
    value: float
    from_unit: str
    to_unit: str
    result: float
    result_display: str
    exact: bool
    method: str
    warnings: list[str]


def _density(ingredient: str | None) -> tuple[str, float] | None:
    if not ingredient:
        return None
    for keywords, label, density in DENSITIES:
        if any(contains_term(ingredient, k) for k in keywords):
            return label, density
    return None


def run(inp: ConversionInput, _: ToolContext) -> ConversionOutput:
    src_key, dst_key = normalize_unit(inp.from_unit), normalize_unit(inp.to_unit)
    for raw, key in ((inp.from_unit, src_key), (inp.to_unit, dst_key)):
        if key is None:
            raise ToolError("unknown_unit", f"Unidad desconocida: '{raw}'. Soportadas: {supported_units_text()}.")
    src, dst = UNITS[src_key], UNITS[dst_key]
    warnings: list[str] = []

    if src.kind == "temperature" or dst.kind == "temperature":
        if src.kind != dst.kind:
            raise ToolError("incompatible_units", "No se puede convertir temperatura a peso o volumen.")
        result = inp.value
        if src_key == "c" and dst_key == "f":
            result = inp.value * 9 / 5 + 32
        elif src_key == "f" and dst_key == "c":
            result = (inp.value - 32) * 5 / 9
        rounded = round(result)
        return ConversionOutput(
            value=inp.value, from_unit=src.label, to_unit=dst.label, result=float(rounded),
            result_display=f"{rounded} {dst.label}", exact=True, method="fórmula °F = °C × 9/5 + 32",
            warnings=["En hornos de convección (con ventilador) suele bajarse unos 15-20 °C."] if rounded >= 100 else [],
        )

    if inp.value < 0:
        raise ToolError("negative_value", "Una cantidad de peso o volumen no puede ser negativa.")

    base = inp.value * src.to_base  # gramos o mililitros
    exact = True
    method = "factor de conversión estándar"
    if src.kind != dst.kind:
        found = _density(inp.ingredient)
        exact = False
        if found:
            label, density = found
            method = f"densidad aproximada de {label}: {density} g/ml"
            warnings.append("Conversión volumen-peso aproximada: depende de cómo se mida (tamizado, compactado). Para precisión, usa báscula.")
        else:
            label, density = "agua", 1.0
            method = "estimación con la densidad del agua (1 g/ml)"
            warnings.append(
                "No hay densidad conocida para este ingrediente"
                + (f" ('{inp.ingredient}')" if inp.ingredient else " (no se indicó cuál)")
                + ": es una ESTIMACIÓN que puede desviarse bastante. Gramos y mililitros no son equivalentes."
            )
        base = base * density if src.kind == "volume" else base / density

    result = base / dst.to_base
    rounded, display = format_amount(result, dst_key)
    if "cup" in (src_key, dst_key):
        warnings.append("Taza estándar de EE. UU. = 236.6 ml; en México/España muchas recetas usan taza de 250 ml.")
    return ConversionOutput(
        value=inp.value, from_unit=src.label, to_unit=dst.label, result=rounded,
        result_display=f"{display} {dst.label}", exact=exact, method=method, warnings=warnings,
    )


TOOL = Tool(
    name="convert_cooking_units",
    description=(
        "Convierte cantidades de cocina entre unidades de peso (g, kg, oz, lb), volumen (ml, l, cucharadita, "
        "cucharada, taza) y temperatura (°C, °F). Para volumen <-> peso indica el ingrediente; si no hay "
        "densidad conocida devuelve una estimación marcada con exact=false."
    ),
    input_model=ConversionInput,
    output_model=ConversionOutput,
    handler=run,
    status_label="Convirtiendo unidades…",
)
