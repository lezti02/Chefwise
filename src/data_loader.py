"""Acceso a los datasets de visualización y modelado.

El orden del CSV de modelado se conserva al unirlo por ``recipe_id`` con los
campos de visualización. Esa posición es el vínculo con la matriz TF-IDF.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import DISPLAY_DATASET_PATH, MODEL_DATASET_PATH
from .exceptions import DatasetNotFoundError, DatasetSchemaError, RecipeNotFoundError
from .text_utils import split_ingredients, split_steps, split_tags

DISPLAY_REQUIRED_COLUMNS = [
    "recipe_id",
    "name",
    "ingredients",
    "instructions",
    "source",
    "url",
]

MODEL_REQUIRED_COLUMNS = [
    "recipe_id",
    "tags",
    "difficulty",
    "total_time_min",
    "country",
    "recipe_text",
]

DISPLAY_OPTIONAL_COLUMNS = [
    "prep_time_min",
    "cook_time_min",
    "servings",
    "num_comments",
    "context",
]


@dataclass
class RecipeStore:
    """Dataset en memoria + vectores numpy precalculados para filtrar rápido."""

    df: pd.DataFrame
    id_to_pos: dict[int, int]
    total_time: np.ndarray  # float, NaN si se desconoce
    tags_by_position: tuple[frozenset[str], ...]
    tags: tuple[str, ...]
    countries: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.df)

    def position_of(self, recipe_id: int) -> int:
        try:
            return self.id_to_pos[int(recipe_id)]
        except (KeyError, ValueError, TypeError):
            raise RecipeNotFoundError(f"No existe la receta con recipe_id={recipe_id}") from None

    def positions_of(self, recipe_ids: list[int]) -> list[int]:
        """Posiciones de los ids que existan (los desconocidos se ignoran)."""
        return [self.id_to_pos[i] for i in recipe_ids if i in self.id_to_pos]

    def summary(self, pos: int) -> dict[str, Any]:
        """Campos para tarjetas/listas."""
        row = self.df.iloc[pos]
        return {
            "recipe_id": int(row["recipe_id"]),
            "name": str(row["name"]),
            "ingredients": split_ingredients(row["ingredients"]),
            "difficulty": _clean_str(row.get("difficulty")),
            "total_time_min": _clean_int(row.get("total_time_min")),
            "servings": _clean_int(row.get("servings")),
            "country": _clean_str(row.get("country")),
            "category": _primary_meal_tag(row.get("tags")),
            "meal_type": _primary_meal_tag(row.get("tags")),
            "source": _clean_str(row.get("source")),
            "source_url": _clean_str(row.get("url")),
        }

    def detail(self, pos: int) -> dict[str, Any]:
        """Receta completa: resumen + pasos y metadatos extra del CSV."""
        row = self.df.iloc[pos]
        return {
            **self.summary(pos),
            "instructions": split_steps(row["instructions"]),
            "difficulty_source": _clean_str(row.get("difficulty")),
            "prep_time_min": _clean_int(row.get("prep_time_min")),
            "cook_time_min": _clean_int(row.get("cook_time_min")),
            "category_tags": split_tags(row.get("tags")),
            "diet_tags": [],
            "description": _clean_str(row.get("context")),
            "num_comments": _clean_int(row.get("num_comments")),
        }


def load_recipes(
    display_path: Path | str = DISPLAY_DATASET_PATH,
    model_path: Path | str = MODEL_DATASET_PATH,
) -> RecipeStore:
    """Une ambos CSV por ID conservando estrictamente el orden del modelo."""
    display_path, model_path = Path(display_path), Path(model_path)
    for path, env_name in (
        (display_path, "CHEFWISE_DISPLAY_DATASET_PATH"),
        (model_path, "CHEFWISE_MODEL_DATASET_PATH"),
    ):
        if path.is_file():
            continue
        raise DatasetNotFoundError(
            f"No se encontró el dataset procesado en: {path}. "
            f"Define {env_name} o coloca el CSV en data/processed/."
        )

    display = _read_csv(display_path, DISPLAY_REQUIRED_COLUMNS, DISPLAY_OPTIONAL_COLUMNS)
    model = _read_csv(model_path, MODEL_REQUIRED_COLUMNS, [])
    _validate_ids(display, display_path)
    _validate_ids(model, model_path)

    display_fields = [*DISPLAY_REQUIRED_COLUMNS, *DISPLAY_OPTIONAL_COLUMNS]
    display_fields = [column for column in display_fields if column in display.columns]
    try:
        df = model.merge(
            display[display_fields],
            on="recipe_id",
            how="left",
            sort=False,
            validate="one_to_one",
            indicator=True,
        )
    except pd.errors.MergeError as exc:
        raise DatasetSchemaError(f"No se pudieron unir los CSV por recipe_id: {exc}") from exc
    missing_ids = df.loc[df["_merge"] != "both", "recipe_id"].tolist()
    if missing_ids:
        raise DatasetSchemaError(
            f"{model_path.name} contiene recipe_id ausentes en {display_path.name}: {missing_ids[:10]}"
        )
    df = df.drop(columns="_merge")
    if not df["recipe_id"].reset_index(drop=True).equals(model["recipe_id"].reset_index(drop=True)):
        raise DatasetSchemaError("La unión alteró el orden de filas de recetas_modelo.csv.")

    id_to_pos = {int(rid): pos for pos, rid in enumerate(df["recipe_id"].to_numpy())}
    tags_by_position = tuple(frozenset(split_tags(value)) for value in df["tags"])
    tags = tuple(sorted({tag for row_tags in tags_by_position for tag in row_tags}))
    countries = tuple(sorted(value for value in df["country"].dropna().astype(str).unique() if value))
    return RecipeStore(
        df=df,
        id_to_pos=id_to_pos,
        total_time=df["total_time_min"].to_numpy(dtype="float64", na_value=np.nan),
        tags_by_position=tags_by_position,
        tags=tags,
        countries=countries,
    )


def _read_csv(path: Path, required: list[str], optional: list[str]) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0).columns
    missing = [column for column in required if column not in header]
    if missing:
        raise DatasetSchemaError(f"Al CSV {path.name} le faltan columnas obligatorias: {missing}")
    return pd.read_csv(path, usecols=required + [column for column in optional if column in header])


def _validate_ids(df: pd.DataFrame, path: Path) -> None:
    if df["recipe_id"].isna().any() or not df["recipe_id"].is_unique:
        raise DatasetSchemaError(f"`recipe_id` debe existir y ser único en {path.name}.")
    try:
        df["recipe_id"] = df["recipe_id"].astype("int64")
    except (TypeError, ValueError) as exc:
        raise DatasetSchemaError(f"`recipe_id` debe contener enteros en {path.name}.") from exc


def _primary_meal_tag(value: Any) -> str | None:
    meal_tags = {"Desayuno", "Comida", "Cena", "Postre", "Bebida"}
    return next((tag.lower() for tag in split_tags(value) if tag in meal_tags), None)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_str(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    number = float(value)
    return None if math.isnan(number) else int(round(number))
