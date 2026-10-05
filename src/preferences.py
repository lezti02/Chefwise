"""Preferencias estructuradas para recomendar recetas."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import DEFAULT_TOP_N

DIFFICULTIES = ("facil", "intermedio", "reto")  # valores de `app_difficulty`


@dataclass(frozen=True)
class UserPreferences:
    """Preferencias ya validadas que recibe el recomendador."""

    tags: tuple[str, ...] = ()
    difficulty: str | None = None  # uno de DIFFICULTIES
    max_time: int | None = None  # minutos
    countries: tuple[str, ...] = ()  # vacío = cualquier país
    exclude_ids: tuple[int, ...] = field(default_factory=tuple)
    top_n: int = DEFAULT_TOP_N

    def __post_init__(self) -> None:
        if self.difficulty is not None and self.difficulty not in DIFFICULTIES:
            raise ValueError(f"Dificultad desconocida: {self.difficulty!r}. Válidas: {DIFFICULTIES}")
        if self.top_n < 1:
            raise ValueError("top_n debe ser >= 1")
