"""Parseo de renglones de ingredientes del CSV ("1 ½ tazas de harina (140 g)").

El dataset guarda cada ingrediente como texto libre. Aquí se separan, cuando se
puede, cantidad, unidad, nombre, notas y si es opcional. Si un renglón no se
puede interpretar, la cantidad queda en None y el texto original (`text`) se
conserva siempre: nunca se inventa una cantidad.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.text_utils import normalize_text

from .units import COUNT_UNITS, normalize_unit, unit_aliases

_UNICODE_FRACTIONS = {
    "½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125,
    "⅜": 0.375, "⅝": 0.625, "⅞": 0.875, "⅕": 0.2,
}
_UF = "[" + "".join(_UNICODE_FRACTIONS) + "]"
_SINGLE = rf"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*{_UF}|\d+\s*/\s*\d+|{_UF}|\d+(?:[.,]\d+)?)"
_AMOUNT_RE = re.compile(rf"^\s*(?P<a>{_SINGLE})(?:\s*(?:-|–)\s*|\s+a\s+)?(?P<b>(?<=[-–\s]){_SINGLE})?")

# Unidades reconocidas al inicio del texto (ya normalizado), de la más larga a la más corta.
_UNIT_WORDS = sorted({*unit_aliases(), *COUNT_UNITS} - {"c", "f", "°c", "ºc", "°f", "ºf"}, key=len, reverse=True)
_UNIT_RE = re.compile(r"^(?P<u>" + "|".join(re.escape(u) for u in _UNIT_WORDS) + r")\.?(?=\s|$|,|\))")

_STOPWORDS = {
    "de", "del", "la", "el", "los", "las", "y", "o", "en", "con", "para", "al", "a", "un", "una", "sin",
    "cortado", "cortada", "cortados", "cortadas", "picado", "picada", "picados", "picadas", "finamente",
    "grande", "grandes", "mediano", "mediana", "medianos", "medianas", "chico", "chica", "pequeno",
    "pequena", "fresco", "fresca", "frescos", "frescas", "tiras", "cubos", "cubitos", "rodajas", "trozos",
    "gusto", "opcional", "molido", "molida", "rallado", "rallada", "entero", "entera", "limpio", "limpia",
    "cocido", "cocida", "cocidos", "cocidas", "natural", "taza", "tazas", "pieza", "piezas", "cucharada",
    "cucharadas", "cucharadita", "cucharaditas", "gramos", "kilo", "kilogramo", "litro", "mililitros",
}


@dataclass(frozen=True)
class ParsedIngredient:
    text: str  # renglón original del CSV
    name: str
    amount: float | None
    amount_max: float | None  # rangos "2-3 dientes"
    unit: str | None  # canónica (g, cup...) o la palabra casera tal cual (diente, pizca...)
    optional: bool
    notes: str | None

    def keywords(self) -> list[str]:
        return ingredient_keywords(self.name)


def parse_number(raw: str) -> float | None:
    s = raw.strip()
    try:
        if m := re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", s):
            return int(m[1]) + int(m[2]) / int(m[3])
        if m := re.fullmatch(rf"(\d+)\s*({_UF})", s):
            return int(m[1]) + _UNICODE_FRACTIONS[m[2]]
        if m := re.fullmatch(r"(\d+)\s*/\s*(\d+)", s):
            return int(m[1]) / int(m[2])
        if s in _UNICODE_FRACTIONS:
            return _UNICODE_FRACTIONS[s]
        return float(s.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


def parse_ingredient(line: str) -> ParsedIngredient:
    text = line.strip()
    rest = text
    amount = amount_max = None

    if m := _AMOUNT_RE.match(rest):
        amount = parse_number(m["a"])
        amount_max = parse_number(m["b"]) if m["b"] else None
        rest = rest[m.end():].strip()

    unit = None
    if amount is not None:
        normalized = normalize_text(rest)
        if um := _UNIT_RE.match(normalized):
            word = um["u"]
            unit = normalize_unit(word) or word
            rest = rest[um.end():].strip()
            rest = re.sub(r"^\.?\s*(?:de|del)\s+", "", rest, flags=re.IGNORECASE)

    optional = "opcional" in normalize_text(text)
    name, notes = _split_notes(rest)
    if normalize_text(name).endswith("al gusto"):
        name = name[: -len("al gusto")].strip(" ,")
        notes = ", ".join(filter(None, ["al gusto", notes]))
    return ParsedIngredient(
        text=text,
        name=name or text,
        amount=amount,
        amount_max=amount_max,
        unit=unit,
        optional=optional,
        notes=notes,
    )


def _split_notes(rest: str) -> tuple[str, str | None]:
    notes: list[str] = []
    for paren in re.findall(r"\(([^)]*)\)", rest):
        if paren.strip():
            notes.append(paren.strip())
    base = re.sub(r"\([^)]*\)", " ", rest)
    name, _, tail = base.partition(",")
    if tail.strip():
        notes.append(tail.strip())
    name = re.sub(r"\s+", " ", name).strip(" .,-")
    return name, "; ".join(notes) or None


def ingredient_keywords(name: str) -> list[str]:
    """Palabras significativas del nombre ("Filete de pescado cortado" -> ['filete', 'pescado'])."""
    words = re.findall(r"[a-zñ]+", normalize_text(name))
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def _singular(word: str) -> str:
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def mentions(text_normalized: str, keyword: str) -> bool:
    """¿El texto menciona la palabra (tolerando plural)?"""
    stem = _singular(keyword)
    return re.search(rf"\b{re.escape(stem)}(?:s|es)?\b", text_normalized) is not None


def contains_term(text: str, term: str) -> bool:
    """¿`text` contiene `term` como palabra/frase completa? ("sal" no coincide con "salsa")."""
    norm = normalize_text(text)
    return re.search(rf"\b{re.escape(normalize_text(term))}(?:s|es)?\b", norm) is not None
