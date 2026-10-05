"""Entrada serverless de Vercel: expone el backend FastAPI bajo el prefijo /api."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import _build_assistant, app as backend_app  # noqa: E402
from src.recommender import Recommender  # noqa: E402

_PREFIX = "/api"


def _ensure_state() -> None:
    """Vercel puede no ejecutar el `lifespan`; carga el recomendador al primer uso."""
    if getattr(backend_app.state, "recommender", None) is None:
        backend_app.state.recommender = Recommender.from_disk()
        backend_app.state.assistant = _build_assistant(backend_app.state.recommender)


async def app(scope, receive, send):
    if scope["type"] == "http":
        _ensure_state()
        path = scope["path"]
        if path.startswith(_PREFIX):
            scope = {**scope, "path": path[len(_PREFIX):] or "/"}
    await backend_app(scope, receive, send)
