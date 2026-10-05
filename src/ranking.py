"""Ranking final de candidatos usando exclusivamente similitud TF-IDF."""

from __future__ import annotations

import numpy as np

def rank_candidates(
    candidate_mask: np.ndarray,
    top_n: int,
    similarity: np.ndarray,
    tag_counts: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (posiciones, scores) de los top_n candidatos, de mayor a menor score.

    Si se proporciona `tag_counts`, prioriza recetas con mayor número de coincidencias
    de etiquetas. A igualdad de coincidencias (o si no se pasa `tag_counts`),
    desempata por similitud TF-IDF y finalmente por posición determinista en el CSV.
    """
    positions = np.flatnonzero(candidate_mask)
    if positions.size == 0:
        return positions, np.empty(0)

    scores = similarity[positions]
    if tag_counts is not None:
        counts = tag_counts[positions]
        order = np.lexsort((positions, -scores, -counts))[:top_n]
    else:
        order = np.lexsort((positions, -scores))[:top_n]
    return positions[order], scores[order]
