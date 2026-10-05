"""Alérgenos y restricciones (mismas reglas que `COMMON_ALLERGENS` del frontend).

Si cambias las palabras clave aquí, cámbialas también en
`frontend/src/app/models/recipe.model.ts` para que el filtro de la app y el
asistente coincidan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.text_utils import normalize_text


@dataclass(frozen=True)
class AllergenRule:
    id: str
    label: str
    keywords: tuple[str, ...]
    exceptions: tuple[str, ...] = ()


ALLERGENS: tuple[AllergenRule, ...] = (
    AllergenRule(
        "lacteos", "Lácteos",
        ("leche", "queso", "yogur", "yogurt", "crema", "mantequilla", "nata", "requeson", "suero de leche",
         "jocoque", "ghee"),
        ("leche de coco", "leche de almendra", "leche de soya", "leche de soja", "leche de avena",
         "leche de arroz", "crema de cacahuate", "crema de mani", "crema de coco"),
    ),
    AllergenRule(
        "gluten", "Gluten",
        ("harina", "trigo", "pan", "pasta", "espagueti", "fideo", "galleta", "cebada", "centeno", "cuscus",
         "seitan", "cerveza", "tortilla de harina", "tortillas de trigo"),
        ("harina de maiz", "harina de arroz", "harina de almendra", "harina de coco", "pasta de tomate",
         "pasta de achiote", "pasta de chile"),
    ),
    AllergenRule("huevo", "Huevo", ("huevo", "yema", "clara de huevo", "mayonesa", "merengue")),
    AllergenRule(
        "frutos-secos", "Frutos secos",
        ("nuez", "nueces", "almendra", "avellana", "pistache", "pistacho", "anacardo", "maranon", "castana",
         "pinon", "pecana"),
        ("nuez moscada",),
    ),
    AllergenRule("cacahuate", "Cacahuate", ("cacahuate", "cacahuete", "mani")),
    AllergenRule(
        "mariscos", "Mariscos",
        ("marisco", "camaron", "gamba", "langosta", "langostino", "cangrejo", "jaiba", "pulpo", "calamar",
         "mejillon", "almeja", "ostion", "ostra", "vieira"),
    ),
    AllergenRule(
        "pescado", "Pescado",
        ("pescado", "salmon", "atun", "bacalao", "sardina", "merluza", "tilapia", "anchoa", "trucha", "robalo",
         "huachinango", "corvina", "lenguado", "mojarra"),
    ),
    AllergenRule("soya", "Soya", ("soya", "soja", "tofu", "edamame", "miso", "tempeh")),
    AllergenRule("sesamo", "Ajonjolí", ("ajonjoli", "sesamo", "tahini", "tahin")),
)

_MEAT = ("carne", "res", "cerdo", "puerco", "pollo", "pavo", "jamon", "tocino", "chorizo", "salchicha",
         "cordero", "ternera", "pechuga", "muslo", "costilla", "lomo", "chuleta", "bistec", "longaniza",
         "panceta", "caldo de pollo", "caldo de res", "gelatina", "grenetina", "manteca de cerdo")

# Restricciones de dieta -> reglas de alérgenos que implican + palabras extra.
_DIETS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "vegetariano": ((("pescado", "mariscos")), _MEAT),
    "vegano": (("pescado", "mariscos", "lacteos", "huevo"), (*_MEAT, "miel")),
    "sin gluten": (("gluten",), ()),
    "celiaco": (("gluten",), ()),
    "sin lactosa": (("lacteos",), ()),
    "sin lacteos": (("lacteos",), ()),
    "sin huevo": (("huevo",), ()),
    "sin alcohol": ((), ("cerveza", "vino", "brandy", "ron", "tequila", "licor", "vodka", "whisky", "mezcal",
                         "jerez", "coñac", "cognac")),
    "sin cerdo": ((), ("cerdo", "puerco", "jamon", "tocino", "chorizo", "panceta", "manteca de cerdo",
                       "longaniza", "chicharron")),
}


def _contains(text_normalized: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(normalize_text(keyword))}(s|es)?\b", text_normalized) is not None


def rule_matches(text: str, rule: AllergenRule) -> bool:
    norm = normalize_text(text)
    for exc in rule.exceptions:
        norm = norm.replace(normalize_text(exc), " ")
    return any(_contains(norm, kw) for kw in rule.keywords)


def find_rule(term: str) -> AllergenRule | None:
    """'Lácteos', 'lacteos', 'leche', 'nueces' -> regla; None si no se reconoce."""
    key = normalize_text(term).strip()
    for rule in ALLERGENS:
        if key in (rule.id, normalize_text(rule.label)) or key in rule.keywords:
            return rule
    return None


@dataclass(frozen=True)
class Restriction:
    """Una alergia o dieta del usuario, traducida a algo comprobable sobre un texto."""

    label: str
    rules: tuple[AllergenRule, ...]
    extra_keywords: tuple[str, ...]

    def matches(self, text: str) -> bool:
        norm = normalize_text(text)
        return any(rule_matches(text, r) for r in self.rules) or any(_contains(norm, k) for k in self.extra_keywords)


def to_restriction(term: str) -> Restriction:
    key = normalize_text(term).strip()
    if key in _DIETS:
        rule_ids, extra = _DIETS[key]
        return Restriction(term, tuple(r for r in ALLERGENS if r.id in rule_ids), extra)
    stripped = key.removeprefix("sin ").removeprefix("alergia a ").removeprefix("alergia al ").strip()
    if rule := find_rule(stripped):
        return Restriction(term, (rule,), ())
    # Término libre ("fresa", "kiwi"): se busca tal cual.
    return Restriction(term, (), (stripped,) if stripped else ())


def matching_lines(lines: list[str], restriction: Restriction) -> list[str]:
    return [line for line in lines if restriction.matches(line)]
