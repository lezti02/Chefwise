"""Perfil de gusto: centroide ponderado y mezcla con la consulta."""

from __future__ import annotations

import numpy as np
from scipy import sparse

from src.profile import (
    BLEND_GENERIC,
    BLEND_INGREDIENTS,
    BLEND_WITH_FILTERS,
    InteractionSignals,
    blend_alpha,
    blend_scores,
    centroid_similarities,
)


def test_weighted_ids_keep_the_strongest_signal():
    signals = InteractionSignals(favorite_ids=(1,), saved_ids=(1, 2), viewed_ids=(1, 3), cooked_ids=(2,))
    weights = signals.weighted_ids()
    assert weights[1] == 3.0
    assert weights[2] == 2.5
    assert weights[3] == 0.6


def test_centroid_ranks_the_liked_neighborhood():
    matrix = np.array(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    similarities = centroid_similarities(matrix, [0], [1.0])
    assert similarities is not None
    assert similarities[1] > similarities[2]


def test_sparse_centroid_matches_dense():
    dense = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.6, 0.8, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    sparse_matrix = sparse.csr_matrix(dense)
    dense_sim = centroid_similarities(dense, [0, 1], [3.0, 1.0])
    sparse_sim = centroid_similarities(sparse_matrix, [0, 1], [3.0, 1.0])
    assert dense_sim is not None and sparse_sim is not None
    np.testing.assert_allclose(dense_sim, sparse_sim)


def test_empty_or_zero_weights_yield_no_profile():
    matrix = np.eye(3)
    assert centroid_similarities(matrix, [], []) is None
    assert centroid_similarities(matrix, [0], [0.0]) is None


def test_blend_scores_and_alpha():
    query = np.array([1.0, 0.0])
    profile = np.array([0.0, 1.0])
    np.testing.assert_allclose(blend_scores(query, None, 0.5), query)
    np.testing.assert_allclose(blend_scores(query, profile, 0.0), query)
    np.testing.assert_allclose(blend_scores(query, profile, 0.5), np.array([0.5, 0.5]))
    assert blend_alpha(generic_query=True) == BLEND_GENERIC
    assert blend_alpha(generic_query=False) == BLEND_WITH_FILTERS
    assert blend_alpha(for_ingredients=True) == BLEND_INGREDIENTS
