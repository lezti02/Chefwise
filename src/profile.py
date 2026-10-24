"""Perfil de gusto a partir de las recetas con las que el usuario ya interactuó.

No hay cuentas en el servidor: el frontend manda los `recipe_id` de favoritas,
guardadas, cocinadas y vistas. Aquí se arma un centroide ponderado en el mismo
espacio que usa "Sorpréndeme" (embeddings o TF-IDF) y se mezcla con la
similitud de la consulta.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

WEIGHTS = {
    "favorite": 3.0,
    "cooked": 2.5,
    "saved": 1.5,
    "viewed": 0.6,
}

# Cuánto pesa el perfil frente a la consulta de la pantalla.
BLEND_WITH_FILTERS = 0.45
BLEND_GENERIC = 0.70
BLEND_INGREDIENTS = 0.35


@dataclass(frozen=True)
class InteractionSignals:
    """Ids que el usuario ya tocó. Un mismo id en varias listas se queda con el mayor peso."""

    favorite_ids: tuple[int, ...] = ()
    saved_ids: tuple[int, ...] = ()
    cooked_ids: tuple[int, ...] = ()
    viewed_ids: tuple[int, ...] = ()

    def weighted_ids(self) -> dict[int, float]:
        weights: dict[int, float] = {}
        for ids, key in (
            (self.viewed_ids, "viewed"),
            (self.saved_ids, "saved"),
            (self.cooked_ids, "cooked"),
            (self.favorite_ids, "favorite"),
        ):
            weight = WEIGHTS[key]
            for recipe_id in ids:
                weights[recipe_id] = max(weights.get(recipe_id, 0.0), weight)
        return weights


def centroid_similarities(
    matrix: np.ndarray | sparse.spmatrix,
    positions: list[int],
    weights: list[float],
) -> np.ndarray | None:
    """Coseno de un centroide ponderado contra todas las recetas (filas L2-normalizadas)."""
    if not positions:
        return None
    weight_vector = np.asarray(weights, dtype=np.float64)
    if weight_vector.size != len(positions) or np.all(weight_vector <= 0):
        return None
    if sparse.issparse(matrix):
        rows = matrix[positions]
        centroid = np.asarray(rows.T.dot(weight_vector)).ravel()
    else:
        centroid = weight_vector @ np.asarray(matrix)[positions]
    norm = float(np.linalg.norm(centroid))
    if norm == 0.0:
        return None
    centroid = centroid / norm
    if sparse.issparse(matrix):
        return np.asarray(matrix.dot(centroid)).ravel()
    return np.asarray(matrix @ centroid).ravel()


def blend_scores(query: np.ndarray, profile: np.ndarray | None, alpha: float) -> np.ndarray:
    if profile is None or alpha <= 0:
        return query
    return (1.0 - alpha) * query + alpha * profile


def blend_alpha(*, generic_query: bool = False, for_ingredients: bool = False) -> float:
    if for_ingredients:
        return BLEND_INGREDIENTS
    return BLEND_GENERIC if generic_query else BLEND_WITH_FILTERS
