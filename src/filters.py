"""Filtros duros sobre el dataset: devuelven máscaras booleanas alineadas con el CSV."""

from __future__ import annotations

import numpy as np

from .data_loader import RecipeStore


def structural_mask(
    store: RecipeStore,
    *,
    difficulty: str | None,
    max_minutes: int | None,
    countries: tuple[str, ...],
    exclude_positions: list[int],
) -> np.ndarray:
    """Filtros que SIEMPRE se respetan: dificultad, tiempo, país y exclusiones.

    Si se pide un tiempo o una dificultad, las recetas sin ese dato en el CSV
    se descartan: no se puede afirmar que cumplan.
    """
    df = store.df
    mask = np.ones(len(df), dtype=bool)

    if difficulty is not None:
        mask &= (df["difficulty"] == difficulty).to_numpy(dtype=bool)
    if max_minutes is not None:
        with np.errstate(invalid="ignore"):
            mask &= store.total_time <= max_minutes  # NaN <= x es False
    if countries:
        mask &= df["country"].isin(countries).to_numpy(dtype=bool)
    if exclude_positions:
        mask[exclude_positions] = False
    return mask


def exact_tags_mask(store: RecipeStore, tags: tuple[str, ...]) -> np.ndarray:
    """Exige que cada receta contenga todas las etiquetas seleccionadas."""
    if not tags:
        return np.ones(len(store), dtype=bool)
    selected = frozenset(tags)
    return np.fromiter(
        (selected.issubset(recipe_tags) for recipe_tags in store.tags_by_position),
        dtype=bool,
        count=len(store),
    )


def tag_match_counts(store: RecipeStore, tags: tuple[str, ...]) -> np.ndarray:
    """Número de etiquetas seleccionadas que contiene cada receta."""
    if not tags:
        return np.zeros(len(store), dtype=int)
    selected = frozenset(tags)
    return np.fromiter(
        (len(selected & recipe_tags) for recipe_tags in store.tags_by_position),
        dtype=int,
        count=len(store),
    )
