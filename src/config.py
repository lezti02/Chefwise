"""Rutas y parámetros del recomendador.

Todo se puede sobreescribir con variables de entorno para no depender del
directorio desde donde se arranca el servicio.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DISPLAY_DATASET_PATH = Path(
    os.getenv(
        "CHEFWISE_DISPLAY_DATASET_PATH",
        PROJECT_ROOT / "data" / "processed" / "recetas_limpias.csv",
    )
)
MODEL_DATASET_PATH = Path(
    os.getenv(
        "CHEFWISE_MODEL_DATASET_PATH",
        PROJECT_ROOT / "data" / "processed" / "recetas_modelo.csv",
    )
)
MODELS_DIR = Path(
    os.getenv("CHEFWISE_MODELS_DIR", PROJECT_ROOT / "models" / "recetas_modelo")
)

# Alias conservado para módulos analíticos que consumen el corpus del modelo.
DATASET_PATH = MODEL_DATASET_PATH

VECTORIZER_FILENAME = "tfidf_vectorizer.joblib"
MATRIX_FILENAME = "recipe_tfidf_matrix.joblib"

DEFAULT_TOP_N = 5
