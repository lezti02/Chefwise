"""Unidades culinarias: alias en español/inglés, factores exactos y formato de cantidades.

Peso se normaliza a gramos y volumen a mililitros. Las tazas/cucharas son las
medidas estándar de EE. UU. (taza = 236.59 ml); en México y España se usa a
menudo la "taza métrica" de 250 ml, lo que se avisa al convertir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from src.text_utils import normalize_text

UnitKind = Literal["weight", "volume", "temperature"]


@dataclass(frozen=True)
class UnitInfo:
    canonical: str
    kind: UnitKind
    to_base: float  # gramos (peso) o mililitros (volumen); 0 para temperatura
    label: str


UNITS: dict[str, UnitInfo] = {
    "mg": UnitInfo("mg", "weight", 0.001, "mg"),
    "g": UnitInfo("g", "weight", 1.0, "g"),
    "kg": UnitInfo("kg", "weight", 1000.0, "kg"),
    "oz": UnitInfo("oz", "weight", 28.349523125, "oz"),
    "lb": UnitInfo("lb", "weight", 453.59237, "lb"),
    "ml": UnitInfo("ml", "volume", 1.0, "ml"),
    "l": UnitInfo("l", "volume", 1000.0, "l"),
    "tsp": UnitInfo("tsp", "volume", 4.92892159375, "cucharadita"),
    "tbsp": UnitInfo("tbsp", "volume", 14.78676478125, "cucharada"),
    "cup": UnitInfo("cup", "volume", 236.5882365, "taza"),
    "c": UnitInfo("c", "temperature", 0.0, "°C"),
    "f": UnitInfo("f", "temperature", 0.0, "°F"),
}

# Alias normalizados (minúsculas, sin acentos) -> unidad canónica.
_ALIASES: dict[str, str] = {
    **{a: "mg" for a in ("mg", "miligramo", "miligramos")},
    **{a: "g" for a in ("g", "gr", "grs", "grm", "gramo", "gramos", "gram", "grams")},
    **{a: "kg" for a in ("kg", "kgs", "kilo", "kilos", "kilogramo", "kilogramos")},
    **{a: "oz" for a in ("oz", "onza", "onzas", "ounce", "ounces")},
    **{a: "lb" for a in ("lb", "lbs", "libra", "libras", "pound", "pounds")},
    **{a: "ml" for a in ("ml", "mililitro", "mililitros", "cc", "cm3")},
    **{a: "l" for a in ("l", "lt", "lts", "litro", "litros", "liter", "liters", "litre")},
    **{
        a: "tsp"
        for a in ("tsp", "cdita", "cditas", "cucharadita", "cucharaditas", "teaspoon", "teaspoons")
    },
    **{
        a: "tbsp"
        for a in (
            "tbsp", "cda", "cdas", "cucharada", "cucharadas", "cucharada sopera",
            "cucharadas soperas", "tablespoon", "tablespoons",
        )
    },
    **{a: "cup" for a in ("cup", "cups", "taza", "tazas")},
    **{a: "c" for a in ("c", "°c", "ºc", "celsius", "centigrados", "grados centigrados", "grados c")},
    **{a: "f" for a in ("f", "°f", "ºf", "fahrenheit", "grados fahrenheit", "grados f")},
}

# Unidades de conteo/caseras: se conservan tal cual (no son convertibles).
COUNT_UNITS = (
    "piezas", "pieza", "pzas", "pza", "pz", "dientes", "diente", "pizcas", "pizca", "latas", "lata",
    "rebanadas", "rebanada", "hojas", "hoja", "manojos", "manojo", "ramitas", "ramita", "sobres", "sobre",
    "paquetes", "paquete", "vasos", "vaso", "chorritos", "chorrito", "chorros", "chorro", "punados",
    "punado", "cabezas", "cabeza", "rodajas", "rodaja", "trozos", "trozo", "unidades", "unidad",
    "cucharas", "cuchara", "cucharones", "cucharon", "tazones", "tazon", "botes", "bote", "frascos", "frasco",
)


def normalize_unit(text: str | None) -> str | None:
    """Unidad canónica (`g`, `cup`, `c`...) o None si no es una unidad convertible conocida."""
    if not text:
        return None
    key = normalize_text(text).strip().rstrip(".").strip()
    return _ALIASES.get(key)


def unit_aliases() -> list[str]:
    return list(_ALIASES)


def supported_units_text() -> str:
    return "peso: g, kg, mg, oz, lb · volumen: ml, l, cucharadita, cucharada, taza · temperatura: °C, °F"


_NICE_FRACTIONS = {
    Fraction(1, 4): "¼", Fraction(1, 3): "⅓", Fraction(1, 2): "½", Fraction(2, 3): "⅔", Fraction(3, 4): "¾",
}


def _fraction_display(value: float) -> tuple[float, str]:
    """Redondea a cuartos/tercios (medidas caseras) y lo muestra como '1 ½'."""
    best = min(
        (Fraction(round(value * d), d) for d in (4, 3)),
        key=lambda f: abs(float(f) - value),
    )
    whole, rest = divmod(best, 1)
    if best == 0:
        return 0.0, "0"
    parts = []
    if whole:
        parts.append(str(int(whole)))
    if rest:
        parts.append(_NICE_FRACTIONS.get(rest, f"{rest.numerator}/{rest.denominator}"))
    return float(best), " ".join(parts)


def format_amount(value: float, unit: str | None) -> tuple[float, str]:
    """Cantidad redondeada de forma culinariamente razonable + texto para mostrar."""
    if value <= 0:
        return 0.0, "0"
    if unit in ("tsp", "tbsp", "cup") or unit is None or unit not in UNITS:
        # Cucharas, tazas, piezas, dientes... -> fracciones caseras.
        if value < 0.2:
            return round(value, 2), _trim(round(value, 2))
        return _fraction_display(value)
    if unit in ("g", "ml"):
        if value < 10:
            rounded = round(value, 1)
        elif value < 100:
            rounded = float(round(value))
        else:
            rounded = float(5 * round(value / 5))
        return rounded, _trim(rounded)
    rounded = round(value, 2)
    return rounded, _trim(rounded)


def _trim(value: float) -> str:
    if math.isclose(value, round(value)):
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")
