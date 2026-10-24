"""Pruebas de los artefactos de embeddings (Modelo 2) sin red ni torch: usan matrices pequeñas."""

from __future__ import annotations

import json

import numpy as np
import pytest

from src import embeddings as emb
from src.config import MODELS_DIR
from src.exceptions import ArtifactMismatchError, ArtifactNotFoundError

MODEL = "dummy/model"
TEXTS = ["tacos de pollo", "ensalada verde", "pastel de chocolate"]


def _write(models_dir, *, model_name=MODEL, texts=TEXTS, matrix=None):
    if matrix is None:
        matrix = np.eye(len(texts), 4, dtype=np.float32)
    np.save(models_dir / emb.EMBEDDINGS_FILENAME, matrix)
    meta = {
        "model_name": model_name,
        "embedding_dim": int(matrix.shape[1]),
        "n_recipes": int(matrix.shape[0]),
        "texts_sha256": emb.text_fingerprint(texts),
        "query_prefix": "query: ",
        "passage_prefix": "passage: ",
    }
    (models_dir / emb.EMBEDDINGS_META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")
    return matrix


def test_prefixes_depend_on_model_family():
    assert emb.default_prefixes("intfloat/multilingual-e5-small") == ("query: ", "passage: ")
    assert emb.default_prefixes("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2") == ("", "")


def test_fingerprint_detects_changes_and_reordering():
    assert emb.text_fingerprint(TEXTS) == emb.text_fingerprint(list(TEXTS))
    assert emb.text_fingerprint(TEXTS) != emb.text_fingerprint(TEXTS[::-1])
    assert emb.text_fingerprint(["ab", "c"]) != emb.text_fingerprint(["a", "bc"])


def test_load_roundtrip_and_cosine_is_dot_product(tmp_path):
    matrix = _write(tmp_path)
    art = emb.load_embedding_artifacts(tmp_path, texts=TEXTS, expected_model_name=MODEL, load_model=False)
    assert art.matrix.shape == (3, 4)
    np.testing.assert_allclose(art.similarities_to_row(0), matrix @ matrix[0])
    assert art.query_prefix == "query: "
    with pytest.raises(RuntimeError):
        art.similarities("texto")  # sin modelo cargado no puede codificar


def test_missing_artifacts_raise(tmp_path):
    with pytest.raises(ArtifactNotFoundError):
        emb.load_embedding_artifacts(tmp_path, expected_model_name=MODEL, load_model=False)


def test_rejects_other_model_other_corpus_and_bad_shape(tmp_path):
    _write(tmp_path)
    with pytest.raises(ArtifactMismatchError, match="modelo configurado"):
        emb.load_embedding_artifacts(tmp_path, expected_model_name="otro/modelo", load_model=False)
    with pytest.raises(ArtifactMismatchError, match="no corresponden"):
        emb.load_embedding_artifacts(tmp_path, texts=TEXTS[::-1], expected_model_name=MODEL, load_model=False)
    with pytest.raises(ArtifactMismatchError, match="recetas"):
        emb.load_embedding_artifacts(tmp_path, texts=TEXTS[:2], expected_model_name=MODEL, load_model=False)

    np.save(tmp_path / emb.EMBEDDINGS_FILENAME, np.zeros((2, 4), dtype=np.float32))
    with pytest.raises(ArtifactMismatchError, match="forma"):
        emb.load_embedding_artifacts(tmp_path, expected_model_name=MODEL, load_model=False)


def test_saved_model1_artifacts_are_untouched_by_model2_paths():
    # El Modelo 2 usa nombres de archivo distintos: no puede pisar los del Modelo 1.
    from src.config import MATRIX_FILENAME, VECTORIZER_FILENAME

    model2 = {emb.EMBEDDINGS_FILENAME, emb.EMBEDDINGS_META_FILENAME, emb.EMBEDDING_MODEL_DIRNAME}
    assert not model2 & {MATRIX_FILENAME, VECTORIZER_FILENAME}


@pytest.mark.skipif(not (MODELS_DIR / emb.EMBEDDINGS_FILENAME).exists(), reason="embeddings aún no generados")
def test_real_embeddings_match_the_csv(csv_df):
    import pandas as pd

    from src.config import DATASET_PATH

    texts = pd.read_csv(DATASET_PATH, usecols=["recipe_text"])["recipe_text"].astype(str).tolist()
    art = emb.load_embedding_artifacts(MODELS_DIR, texts=texts, load_model=False)
    assert art.matrix.shape[0] == len(texts)
    norms = np.linalg.norm(art.matrix, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-4)


class _FakeEmbeddings:
    """Embeddings falsos: favorecen siempre a la receta en la posición `favorite`."""

    def __init__(self, n: int, favorite: int):
        self.matrix = np.zeros((n, 2), dtype=np.float32)
        self.favorite = favorite
        self.queries: list[str] = []

    def similarities(self, text: str) -> np.ndarray:
        self.queries.append(text)
        sims = np.full(self.matrix.shape[0], 0.1)
        sims[self.favorite] = 0.9
        return sims


def test_surprise_uses_embeddings_but_ingredients_stay_tfidf(client):
    from src.preferences import UserPreferences

    rec = client.app.state.recommender
    fake = _FakeEmbeddings(len(rec.store), favorite=123)
    original = rec.embeddings
    rec.embeddings = fake
    try:
        top = rec.recommend(UserPreferences(top_n=1)).items[0]
        assert top.summary["recipe_id"] == rec.store.df["recipe_id"].iat[123]
        assert fake.queries

        rec.recommend_by_ingredients(["pollo", "arroz"])
        assert len(fake.queries) == 1  # "Con lo que tengo" no pasó por los embeddings
    finally:
        rec.embeddings = original


def test_recommender_falls_back_to_tfidf_without_usable_embeddings(tmp_path):
    from src.recommender import _try_load_embeddings

    class _Store:
        df = __import__("pandas").DataFrame({"recipe_text": ["a", "b"]})

    assert _try_load_embeddings(tmp_path, _Store()) is None
