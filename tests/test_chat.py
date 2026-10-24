"""POST /chat con un proveedor falso y los datos REALES del CSV (sin red)."""

from __future__ import annotations

import json

import pytest

from backend.assistant import ChatUnavailableError, ChefWiseAssistant, RecommenderRepository, default_registry
from backend.assistant.providers.base import ProviderResult


class FakeProvider:
    def __init__(self, reply: str = "Respuesta de prueba", error: str | None = None) -> None:
        self.reply_text = reply
        self.error = error
        self.calls: list[dict] = []

    def run(self, system, context, turns, tools, tool_ctx):
        self.calls.append({"system": system, "context": context, "turns": turns, "tool_ctx": tool_ctx})
        if self.error:
            raise ChatUnavailableError(self.error)
        return ProviderResult(text=self.reply_text)


@pytest.fixture
def fake_provider(client):
    original = client.app.state.assistant
    fake = FakeProvider()
    client.app.state.assistant = ChefWiseAssistant(
        fake, RecommenderRepository(client.app.state.recommender), default_registry()
    )
    yield fake
    client.app.state.assistant = original


def _context(call) -> dict:
    return json.loads(call["context"].split("\n", 1)[1])


def test_chat_sends_open_recipe_as_structured_context(client, csv_df, fake_provider):
    row = csv_df.iloc[0]
    response = client.post("/chat", json={"message": "¿Con qué sustituyo la cebolla?", "recipe_id": int(row["recipe_id"])})
    assert response.status_code == 200
    assert response.json() == {"reply": "Respuesta de prueba"}

    call = fake_provider.calls[-1]
    recipe = _context(call)["recipe"]
    assert recipe["name"] == row["name"] and recipe["steps"] and recipe["ingredients"]
    assert row["name"] not in call["system"]  # la receta no va dentro del system prompt
    assert call["tool_ctx"].current_recipe_id == int(row["recipe_id"])
    assert [t.text for t in call["turns"]] == ["¿Con qué sustituyo la cebolla?"]


def test_chat_sends_visible_recipes_history_and_allergies(client, csv_df, fake_provider):
    ids = [int(i) for i in csv_df["recipe_id"].iloc[:3]]
    history = [
        {"role": "bot", "text": "Saludo inicial"},
        {"role": "user", "text": "Hola"},
        {"role": "bot", "text": "¡Hola!"},
    ]
    body = {"message": "¿Cuál es más rápida?", "history": history, "visible_recipe_ids": ids, "allergies": ["Gluten"]}
    assert client.post("/chat", json=body).status_code == 200

    call = fake_provider.calls[-1]
    ctx = _context(call)
    assert [v["recipe_id"] for v in ctx["visible_recipes"]] == ids
    assert ctx["user"]["allergies"] == ["Gluten"]
    assert [t.role for t in call["turns"]] == ["user", "bot", "user"]


def test_chat_ignores_unknown_recipe(client, fake_provider):
    assert client.post("/chat", json={"message": "Hola", "recipe_id": 999_999_999}).status_code == 200
    assert "recipe" not in _context(fake_provider.calls[-1])


def test_chat_provider_error_is_503_with_safe_message(client, fake_provider):
    fake_provider.error = "El asistente alcanzó su límite de uso gratuito."
    response = client.post("/chat", json={"message": "Hola"})
    assert response.status_code == 503
    assert response.json() == {"detail": "El asistente alcanzó su límite de uso gratuito."}


def test_chat_without_api_key_is_503(client):
    original = client.app.state.assistant
    client.app.state.assistant = None
    try:
        response = client.post("/chat", json={"message": "Hola"})
    finally:
        client.app.state.assistant = original
    assert response.status_code == 503


def test_chat_validates_request(client, fake_provider):
    assert client.post("/chat", json={"message": ""}).status_code == 422
    assert client.post("/chat", json={"message": "x", "visible_recipe_ids": list(range(1, 14))}).status_code == 422
    assert client.post("/chat", json={"message": "x", "current_step": 0}).status_code == 422
    assert client.post("/chat", json={"message": "x", "allergies": ["a" * 61]}).status_code == 422
