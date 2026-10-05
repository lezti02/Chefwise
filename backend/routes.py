"""Endpoints HTTP. Toda la lógica de recomendación vive en `src/`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from src.preferences import UserPreferences
from src.recommender import RecommendationResult, Recommender

from .assistant import ChatQuery, ChatUnavailableError, ChefWiseAssistant, Turn
from .schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    IngredientsRequest,
    MetadataResponse,
    RecipeResponse,
    RecommendationItem,
    RecommendationMeta,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter()


def get_recommender(request: Request) -> Recommender:
    """El recomendador se crea una vez en el arranque (ver `main.lifespan`)."""
    return request.app.state.recommender


RecommenderDep = Annotated[Recommender, Depends(get_recommender)]


def _to_response(result: RecommendationResult) -> RecommendationResponse:
    return RecommendationResponse(
        recommendations=[
            RecommendationItem(
                **item.summary,
                similarity=item.similarity,
                score=item.score,
                matched_ingredients=item.usage.matched if item.usage else None,
                extra_ingredients=item.usage.extras if item.usage else None,
            )
            for item in result.items
        ],
        meta=RecommendationMeta(
            candidates=result.candidates,
            query_text=result.query_text,
            applied_max_time=result.max_minutes,
            relaxed=result.relaxed,
            has_more=result.has_more,
            ingredients_total=result.ingredients_total,
            best_match_count=result.best_match_count,
        ),
    )


@router.get("/health", response_model=HealthResponse, tags=["sistema"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/recommendations", response_model=RecommendationResponse, tags=["recomendaciones"])
def recommendations(body: RecommendationRequest, recommender: RecommenderDep) -> RecommendationResponse:
    prefs = UserPreferences(
        tags=tuple(body.tags),
        difficulty=body.difficulty,
        max_time=body.max_time,
        countries=tuple(body.countries),
        exclude_ids=tuple(body.exclude_ids),
        top_n=body.top_n,
    )
    try:
        return _to_response(recommender.recommend(prefs))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/recommendations/by-ingredients", response_model=RecommendationResponse, tags=["recomendaciones"])
def recommendations_by_ingredients(body: IngredientsRequest, recommender: RecommenderDep) -> RecommendationResponse:
    try:
        result = recommender.recommend_by_ingredients(
            body.ingredients,
            exclude_ids=tuple(body.exclude_ids),
            top_n=body.top_n,
            offset=body.offset,
            fewest_extras=body.fewest_extras,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(result)


@router.get("/metadata", response_model=MetadataResponse, tags=["recetas"])
def metadata(recommender: RecommenderDep) -> MetadataResponse:
    return MetadataResponse(**recommender.metadata())


@router.get("/recipes/search", response_model=RecommendationResponse, tags=["recetas"])
def search_recipes(
    recommender: RecommenderDep,
    q: Annotated[str, Query(min_length=1)],
    tag: Annotated[str | None, Query()] = None,
    top_n: Annotated[int, Query(ge=1, le=50)] = 5,
    offset: Annotated[int, Query(ge=0, le=5000)] = 0,
) -> RecommendationResponse:
    try:
        return _to_response(recommender.search(q, tag=tag, top_n=top_n, offset=offset))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/recipes/{recipe_id}",
    response_model=RecipeResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["recetas"],
)
def get_recipe(
    recommender: RecommenderDep,
    recipe_id: Annotated[int, Path(ge=1, description="recipe_id del dataset")],
) -> RecipeResponse:
    return RecipeResponse(**recommender.get_recipe(recipe_id))


def get_assistant(request: Request) -> ChefWiseAssistant:
    assistant = request.app.state.assistant
    if assistant is None:
        raise ChatUnavailableError("El asistente no está configurado en el servidor.")
    return assistant


AssistantDep = Annotated[ChefWiseAssistant, Depends(get_assistant)]


@router.post("/chat", response_model=ChatResponse, responses={503: {"model": ErrorResponse}}, tags=["chat"])
def chat(body: ChatRequest, assistant: AssistantDep) -> ChatResponse:
    """ChefWise: responde con el contexto de la receta abierta / en pantalla y sus herramientas."""
    query = ChatQuery(
        message=body.message,
        history=[Turn(t.role, t.text) for t in body.history],
        recipe_id=body.recipe_id,
        visible_recipe_ids=body.visible_recipe_ids,
        allergies=body.allergies,
        current_step=body.current_step,
    )
    return ChatResponse(reply=assistant.reply(query))
