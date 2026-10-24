"""Servicio de recomendación Content-Based (similitud coseno).

Los filtros son duros. El ranking depende de la pantalla:
- "Con lo que tengo" y la búsqueda usan SIEMPRE TF-IDF (coincidencia literal de ingredientes);
- "Sorpréndeme" usa embeddings (similitud semántica) si están disponibles y, si no
  (p. ej. en producción, sin torch), cae a TF-IDF.

Si el frontend manda recetas favoritas, guardadas, cocinadas o vistas, el ranking
mezcla esa similitud de consulta con un perfil (centroide ponderado) del usuario.

Se instancia UNA vez al arrancar el backend: el CSV y los artefactos de
`models/` se cargan en memoria y se reutilizan en cada petición.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .config import DEFAULT_TOP_N, DISPLAY_DATASET_PATH, MODEL_DATASET_PATH, MODELS_DIR
from .data_loader import RecipeStore, load_recipes
from .embeddings import EmbeddingArtifacts, load_embedding_artifacts
from .filters import exact_tags_mask, structural_mask, tag_match_counts
from .ingredient_match import IngredientUsage, query_terms, usage
from .models import TfidfArtifacts, load_artifacts, validate_alignment
from .preferences import UserPreferences
from .profile import InteractionSignals, blend_alpha, blend_scores, centroid_similarities
from .ranking import rank_candidates
from .text_utils import split_ingredients

logger = logging.getLogger(__name__)

# Cuántas recetas (las más parecidas) se reordenan en "Con lo que tengo"; también
# es el tope de lo que se puede paginar.
INGREDIENT_POOL = 500


@dataclass
class ScoredRecipe:
    summary: dict[str, Any]
    similarity: float | None
    score: float
    usage: IngredientUsage | None = None  # solo en "Con lo que tengo"


@dataclass
class RecommendationResult:
    items: list[ScoredRecipe]
    candidates: int
    query_text: str | None
    max_minutes: int | None
    relaxed: list[str] = field(default_factory=list)
    has_more: bool = False  # hay más resultados después de esta página
    ingredients_total: int | None = None  # ingredientes distintos que escribió el usuario
    best_match_count: int | None = None  # lo máximo que una receta usa de ellos
    personalized: bool = False  # el ranking usó recetas con las que el usuario ya interactuó


class Recommender:
    def __init__(
        self,
        store: RecipeStore,
        artifacts: TfidfArtifacts,
        *,
        embeddings: EmbeddingArtifacts | None = None,
        validate: bool = True,
    ) -> None:
        if validate:
            validate_alignment(artifacts, store.df["recipe_text"].fillna("").astype(str).tolist())
        if embeddings is not None and embeddings.matrix.shape[0] != len(store):
            raise ValueError(f"Hay {embeddings.matrix.shape[0]} embeddings pero {len(store)} recetas.")
        self.store = store
        self.artifacts = artifacts
        self.embeddings = embeddings

    @classmethod
    def from_disk(
        cls,
        display_dataset_path: Path | str = DISPLAY_DATASET_PATH,
        model_dataset_path: Path | str = MODEL_DATASET_PATH,
        models_dir: Path | str = MODELS_DIR,
        *,
        use_embeddings: bool | None = None,
    ) -> "Recommender":
        """`use_embeddings=None` lo decide CHEFWISE_USE_EMBEDDINGS (por defecto, sí si se pueden cargar)."""
        store = load_recipes(display_dataset_path, model_dataset_path)
        artifacts = load_artifacts(models_dir)
        if use_embeddings is None:
            use_embeddings = os.getenv("CHEFWISE_USE_EMBEDDINGS", "1").lower() not in ("0", "false", "no")
        embeddings = _try_load_embeddings(models_dir, store) if use_embeddings else None
        logger.info(
            "Recomendador listo: %d recetas, %d términos TF-IDF, Sorpréndeme con %s",
            len(store),
            artifacts.matrix.shape[1],
            "embeddings" if embeddings else "TF-IDF",
        )
        return cls(store, artifacts, embeddings=embeddings)

    # ------------------------------------------------------------------ recetas

    def get_recipe(self, recipe_id: int) -> dict[str, Any]:
        """Receta completa. Lanza `RecipeNotFoundError` si no existe."""
        return self.store.detail(self.store.position_of(recipe_id))

    def metadata(self) -> dict[str, list[str]]:
        return {"tags": list(self.store.tags), "countries": list(self.store.countries)}

    # ------------------------------------------------------------ recomendación

    def recommend(self, prefs: UserPreferences) -> RecommendationResult:
        """Top-N para "Sorpréndeme" a partir de las preferencias estructuradas."""
        self._validate_exact_values(prefs.tags, prefs.countries)
        base = structural_mask(
            self.store,
            difficulty=prefs.difficulty,
            max_minutes=prefs.max_time,
            countries=prefs.countries,
            exclude_positions=self.store.positions_of(list(prefs.exclude_ids)),
        )
        query_text = self._preference_query(prefs)
        similarity = (self.embeddings or self.artifacts).similarities(query_text)
        profile_sim = self._profile_similarities(prefs)
        ranking = blend_scores(
            similarity,
            profile_sim,
            blend_alpha(generic_query=query_text == "receta") if profile_sim is not None else 0.0,
        )

        if not prefs.tags:
            return self._build_result(
                base,
                similarity,
                prefs.top_n,
                query_text=query_text,
                max_minutes=prefs.max_time,
                relaxed=[],
                ranking=ranking,
                personalized=profile_sim is not None,
            )

        tag_counts = tag_match_counts(self.store, prefs.tags)
        n_tags = len(prefs.tags)
        all_mask = base & (tag_counts == n_tags)
        any_mask = base & (tag_counts > 0)

        all_count = int(all_mask.sum())
        any_count = int(any_mask.sum())

        if all_count >= prefs.top_n:
            candidates = all_mask
            counts_to_rank = None
            relaxed: list[str] = []
        elif all_count > 0:
            candidates = any_mask
            counts_to_rank = tag_counts
            relaxed = [
                "Se priorizaron las recetas con todas las categorías y se completó con coincidencias parciales."
            ]
        elif any_count > 0:
            candidates = any_mask
            counts_to_rank = tag_counts
            relaxed = [
                "No hay recetas que cumplan todas las categorías; se muestran las que cumplen al menos una."
            ]
        else:
            candidates = np.zeros(len(self.store), dtype=bool)
            counts_to_rank = None
            relaxed = []

        return self._build_result(
            candidates,
            similarity,
            prefs.top_n,
            query_text=query_text,
            max_minutes=prefs.max_time,
            relaxed=relaxed,
            tag_counts=counts_to_rank,
            ranking=ranking,
            personalized=profile_sim is not None,
        )

    def recommend_by_ingredients(
        self,
        ingredients: list[str],
        *,
        exclude_ids: tuple[int, ...] = (),
        top_n: int = DEFAULT_TOP_N,
        offset: int = 0,
        fewest_extras: bool = False,
        max_minutes: int | None = None,
        favorite_ids: tuple[int, ...] = (),
        saved_ids: tuple[int, ...] = (),
        cooked_ids: tuple[int, ...] = (),
        viewed_ids: tuple[int, ...] = (),
    ) -> RecommendationResult:
        """"Con lo que tengo": similitud TF-IDF entre los ingredientes escritos y cada receta.

        Cada resultado trae cuáles de los ingredientes del usuario usa y cuántos
        ingredientes extra necesita. Con `fewest_extras` se ordena primero por cuántos de
        sus ingredientes aprovecha y, a igual aprovechamiento, por menos extras; sin él,
        solo por similitud (no importa cuántos extras lleve).
        `offset` pagina sobre ese mismo orden. `max_minutes` (opcional) descarta
        recetas más largas o sin tiempo conocido.
        """
        terms = query_terms(ingredients)
        if not terms:
            raise ValueError("Se requiere al menos un ingrediente.")
        query_text = " ".join(raw for raw, _ in terms)

        similarity = self.artifacts.similarities(query_text)
        mask = np.ones(len(self.store), dtype=bool)
        if max_minutes is not None:
            with np.errstate(invalid="ignore"):
                mask &= self.store.total_time <= max_minutes
        exclude_positions = self.store.positions_of(list(exclude_ids))
        if exclude_positions:
            mask[exclude_positions] = False
        mask &= similarity > 0  # sin ningún término en común no es una recomendación

        # Se reordena solo el grupo de recetas más parecidas: calcular los extras
        # de todo el catálogo no hace falta y las menos parecidas no se mostrarían.
        positions, scores = rank_candidates(mask, INGREDIENT_POOL, similarity)
        profile_sim = self._profile_similarities(
            UserPreferences(
                favorite_ids=favorite_ids,
                saved_ids=saved_ids,
                cooked_ids=cooked_ids,
                viewed_ids=viewed_ids,
            ),
            space=self.artifacts,
        )
        if profile_sim is not None:
            scores = blend_scores(scores, profile_sim[positions], blend_alpha(for_ingredients=True))
        ingredients_column = self.store.df["ingredients"]
        entries = [
            (int(pos), float(score), usage(terms, split_ingredients(ingredients_column.iat[int(pos)])))
            for pos, score in zip(positions, scores)
        ]
        best_match_count = max((len(u.matched) for _, _, u in entries), default=0)
        if fewest_extras:
            entries = [e for e in entries if e[2].matched]
            entries.sort(key=lambda e: (-len(e[2].matched), e[2].extras, -e[1], e[0]))
        elif profile_sim is not None:
            entries.sort(key=lambda e: (-e[1], e[0]))

        page = entries[offset : offset + top_n]
        items = [
            ScoredRecipe(
                summary=self.store.summary(pos),
                similarity=round(float(similarity[pos]), 4),
                score=round(score, 4),
                usage=u,
            )
            for pos, score, u in page
        ]
        return RecommendationResult(
            items=items,
            candidates=int(mask.sum()),
            query_text=query_text,
            max_minutes=max_minutes,
            has_more=offset + top_n < len(entries),
            ingredients_total=len(terms),
            best_match_count=best_match_count,
            personalized=profile_sim is not None,
        )

    def search(
        self, query: str, *, tag: str | None = None, top_n: int = DEFAULT_TOP_N, offset: int = 0
    ) -> RecommendationResult:
        query_text = query.strip()
        if not query_text:
            raise ValueError("q no puede estar vacío.")
        tags = (tag,) if tag is not None else ()
        self._validate_exact_values(tags, ())
        candidates = exact_tags_mask(self.store, tags)
        similarity = self.artifacts.similarities(query_text)
        candidates &= similarity > 0
        return self._build_result(
            candidates, similarity, top_n, query_text=query_text, max_minutes=None, relaxed=[], offset=offset
        )

    # ----------------------------------------------------------------- internos

    def _validate_exact_values(self, tags: tuple[str, ...], countries: tuple[str, ...]) -> None:
        unknown_tags = [tag for tag in tags if tag not in self.store.tags]
        if unknown_tags:
            raise ValueError(f"Tags desconocidos: {unknown_tags}.")
        unknown_countries = [country for country in countries if country not in self.store.countries]
        if unknown_countries:
            raise ValueError(f"Países desconocidos: {unknown_countries}.")

    @staticmethod
    def _preference_query(prefs: UserPreferences) -> str:
        terms = [*prefs.tags]
        if prefs.difficulty:
            terms.append(prefs.difficulty)
        if prefs.max_time is not None:
            terms.append("receta rapida")
        terms.extend(prefs.countries)
        return " ".join(terms) or "receta"

    def _profile_similarities(self, prefs: UserPreferences, *, space: Any | None = None) -> np.ndarray | None:
        """Similitud de cada receta al centroide de lo que el usuario ya marcó o cocinó."""
        signals = InteractionSignals(
            favorite_ids=prefs.favorite_ids,
            saved_ids=prefs.saved_ids,
            cooked_ids=prefs.cooked_ids,
            viewed_ids=prefs.viewed_ids,
        )
        weights_by_id = signals.weighted_ids()
        positions: list[int] = []
        weights: list[float] = []
        for recipe_id, weight in weights_by_id.items():
            pos = self.store.id_to_pos.get(recipe_id)
            if pos is not None:
                positions.append(pos)
                weights.append(weight)
        matrix = (space or self.embeddings or self.artifacts).matrix
        return centroid_similarities(matrix, positions, weights)

    def _build_result(
        self,
        candidate_mask: np.ndarray,
        similarity: np.ndarray,
        top_n: int,
        *,
        query_text: str | None,
        max_minutes: int | None,
        relaxed: list[str],
        offset: int = 0,
        tag_counts: np.ndarray | None = None,
        ranking: np.ndarray | None = None,
        personalized: bool = False,
    ) -> RecommendationResult:
        total = int(candidate_mask.sum())
        positions, scores = rank_candidates(
            candidate_mask, offset + top_n, ranking if ranking is not None else similarity, tag_counts=tag_counts
        )
        positions, scores = positions[offset:], scores[offset:]
        items = [
            ScoredRecipe(
                summary=self.store.summary(int(pos)),
                similarity=round(float(similarity[pos]), 4),
                score=round(float(score), 4),
            )
            for pos, score in zip(positions, scores)
        ]
        return RecommendationResult(
            items=items,
            candidates=total,
            query_text=query_text,
            max_minutes=max_minutes,
            relaxed=relaxed,
            has_more=offset + top_n < total,
            personalized=personalized,
        )


def _try_load_embeddings(models_dir: Path | str, store: RecipeStore) -> EmbeddingArtifacts | None:
    """Embeddings si el entorno puede usarlos; si no, None y "Sorpréndeme" sigue con TF-IDF.

    Pueden faltar el archivo (no se sube a producción), `sentence-transformers`/torch, o no
    corresponder al CSV actual: ninguno de esos casos debe impedir que arranque el backend.
    """
    try:
        texts = store.df["recipe_text"].fillna("").astype(str).tolist()
        return load_embedding_artifacts(models_dir, texts=texts)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo aquí es degradable
        logger.warning("Sin embeddings para Sorpréndeme (%s: %s); se usa TF-IDF.", type(exc).__name__, exc)
        return None
