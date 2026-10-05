"""Google AI Studio (Gemini API, plan gratuito) vía REST, con function calling."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..tools import ToolCallRecord, ToolContext, ToolRegistry
from .base import ChatUnavailableError, ProviderResult, Turn

logger = logging.getLogger("chefwise.assistant.gemini")

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_UNAVAILABLE = "El asistente no está disponible en este momento. Inténtalo de nuevo."
_NO_ANSWER = "No pude responder a eso. ¿Puedes reformular la pregunta?"


class GeminiProvider:
    MAX_TOOL_ROUNDS = 4  # rondas de herramientas antes de forzar una respuesta de texto
    MAX_CALLS_PER_ROUND = 4

    def __init__(self, api_key: str, model: str, timeout: float, client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = client or httpx.Client()

    def run(
        self, system: str, context: str, turns: list[Turn], tools: ToolRegistry, tool_ctx: ToolContext
    ) -> ProviderResult:
        contents: list[dict[str, Any]] = [
            {"role": "model" if t.role == "bot" else "user", "parts": [{"text": t.text}]} for t in turns
        ]
        declarations = [
            {"name": d["name"], "description": d["description"], "parametersJsonSchema": d["parameters"]}
            for d in tools.declarations()
        ]
        records: list[ToolCallRecord] = []

        for round_no in range(self.MAX_TOOL_ROUNDS + 1):
            final_round = round_no == self.MAX_TOOL_ROUNDS
            body: dict[str, Any] = {
                # Instrucciones y datos van en partes separadas; el contexto nunca se mezcla con el prompt.
                "system_instruction": {"parts": [{"text": system}, {"text": context}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
            }
            if declarations:
                body["tools"] = [{"functionDeclarations": declarations}]
                body["toolConfig"] = {"functionCallingConfig": {"mode": "NONE" if final_round else "AUTO"}}

            candidate = self._generate(body)
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            calls = [p["functionCall"] for p in parts if isinstance(p.get("functionCall"), dict)]

            if calls and not final_round:
                # Se reenvía el turno del modelo tal cual (incluye thoughtSignature, obligatorio en Gemini 3).
                contents.append({"role": "model", "parts": parts})
                responses = []
                for call in calls[: self.MAX_CALLS_PER_ROUND]:
                    name = str(call.get("name", ""))
                    result, record = tools.execute(name, call.get("args"), tool_ctx)
                    records.append(record)
                    response: dict[str, Any] = {"name": name, "response": result}
                    if call.get("id"):
                        response["id"] = call["id"]
                    responses.append({"functionResponse": response})
                contents.append({"role": "user", "parts": responses})
                continue

            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if not text:
                logger.warning("Gemini sin texto (finishReason=%s)", candidate.get("finishReason"))
                raise ChatUnavailableError(_NO_ANSWER)
            return ProviderResult(
                text=text,
                truncated=candidate.get("finishReason") == "MAX_TOKENS",
                tool_calls=records,
                rounds=round_no + 1,
            )
        raise ChatUnavailableError(_NO_ANSWER)  # inalcanzable: la última ronda no permite herramientas

    def _generate(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(
                _URL.format(model=self._model),
                headers={"x-goog-api-key": self._api_key},
                json=body,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            logger.warning("Gemini no respondió: %s", type(exc).__name__)
            raise ChatUnavailableError(_UNAVAILABLE) from exc

        if response.status_code == 429:
            raise ChatUnavailableError(
                "El asistente alcanzó su límite de uso gratuito. Espera un momento e inténtalo de nuevo."
            )
        if response.status_code != 200:
            # Solo el estado y el mensaje de error de Google (sin la key, que va en cabecera).
            logger.error("Gemini respondió %s: %s", response.status_code, response.text[:300])
            raise ChatUnavailableError(_UNAVAILABLE)

        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            logger.warning("Gemini sin candidatos: %s", data.get("promptFeedback"))
            raise ChatUnavailableError(_NO_ANSWER)
        return candidates[0]
