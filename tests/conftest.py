"""Fixtures compartidas. El recomendador real (CSV + artefactos) se carga una vez por sesión."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from src.config import DISPLAY_DATASET_PATH, MODEL_DATASET_PATH


@pytest.fixture(scope="session")
def client():
    # `with` ejecuta el lifespan: carga el CSV y los artefactos reales.
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def display_df() -> pd.DataFrame:
    return pd.read_csv(
        DISPLAY_DATASET_PATH,
        usecols=["recipe_id", "name", "ingredients", "instructions", "url"],
    )


@pytest.fixture(scope="session")
def model_df() -> pd.DataFrame:
    return pd.read_csv(
        MODEL_DATASET_PATH,
        usecols=["recipe_id", "name", "tags", "difficulty", "total_time_min", "country", "recipe_text"],
    )


@pytest.fixture(scope="session")
def csv_df(display_df: pd.DataFrame, model_df: pd.DataFrame) -> pd.DataFrame:
    """Catálogo unido independientemente, en el orden exacto del CSV de modelo."""
    return model_df.merge(display_df, on=["recipe_id", "name"], how="left", validate="one_to_one", sort=False)
