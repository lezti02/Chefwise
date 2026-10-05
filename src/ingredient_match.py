"""Cuántos de los ingredientes del usuario usa una receta, y cuántos le sobran.

Los renglones de la receta son texto libre ("3 dientes de ajo", "1/2 Cebolla"),
así que se compara por palabras: un ingrediente del usuario ("ajo", "pechuga de
pollo") coincide con un renglón cuando todas sus palabras con contenido aparecen
en él, sin importar acentos, mayúsculas ni singular/plural.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_WORD = re.compile(r"[a-zñ0-9]+")
_STOPWORDS = frozenset({"de", "del", "la", "el", "los", "las", "en", "y", "o", "con", "para", "al", "un", "una"})


def _strip_accents(text: str) -> str:
    # La ñ se conserva: "año" y "ano" no son la misma palabra.
    text = text.lower().replace("ñ", "\0")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn").replace("\0", "ñ")


def _stem(word: str) -> str:
    """Quita plural simple (-s) y la -e final: tomate/tomates/Tomates → tomat."""
    if len(word) > 3 and word.endswith("s"):
        word = word[:-1]
    if len(word) > 3 and word.endswith("e"):
        word = word[:-1]
    return word


def _stems(text: str) -> frozenset[str]:
    return frozenset(_stem(w) for w in _WORD.findall(_strip_accents(text)) if w not in _STOPWORDS)


def query_terms(ingredients: list[str]) -> list[tuple[str, frozenset[str]]]:
    """(texto original, palabras) de cada ingrediente escrito; descarta los vacíos y repetidos."""
    seen: set[frozenset[str]] = set()
    terms: list[tuple[str, frozenset[str]]] = []
    for raw in ingredients:
        stems = _stems(raw)
        if stems and stems not in seen:
            seen.add(stems)
            terms.append((raw.strip(), stems))
    return terms


@dataclass(frozen=True)
class IngredientUsage:
    matched: list[str]  # ingredientes del usuario que la receta sí usa (como los escribió)
    extras: int  # renglones de la receta que no corresponden a nada de lo que tiene


def usage(terms: list[tuple[str, frozenset[str]]], recipe_lines: list[str]) -> IngredientUsage:
    line_stems = [_stems(line) for line in recipe_lines]
    matched = [raw for raw, stems in terms if any(stems <= ls for ls in line_stems)]
    extras = sum(1 for ls in line_stems if not any(stems <= ls for _, stems in terms))
    return IngredientUsage(matched=matched, extras=extras)
