"""ChefWise: asistente culinario (prompt, contexto de receta, herramientas y proveedor de IA).

Módulos:
- prompt.py      system prompt centralizado (sin datos de recetas)
- context.py     RECIPE_CONTEXT estructurado a partir de los datos reales
- recipes.py     acceso a recetas (adaptador sobre el recomendador)
- tools/         herramientas: definición, validación y ejecución
- knowledge/     datos curados (sustituciones, seguridad alimentaria)
- providers/     IA (Gemini) con bucle de function calling
- service.py     orquestación, saneado de respuestas y logging
"""

from .providers import ChatProvider, ChatUnavailableError, Turn, build_provider
from .recipes import RecommenderRepository
from .service import ChatQuery, ChefWiseAssistant
from .tools import default_registry

__all__ = [
    "ChatProvider",
    "ChatQuery",
    "ChatUnavailableError",
    "ChefWiseAssistant",
    "RecommenderRepository",
    "Turn",
    "build_provider",
    "default_registry",
]
