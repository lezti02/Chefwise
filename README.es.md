# ChefWise: recomendador de recetas con asistente de cocina con IA

[English](README.md) | **Español**

[![CI](https://github.com/lezti02/Chefwise/actions/workflows/ci.yml/badge.svg)](https://github.com/lezti02/Chefwise/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Angular](https://img.shields.io/badge/Angular-22-DD0031?logo=angular&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.9-F7931E?logo=scikitlearn&logoColor=white)

🌐 **Pruébalo en línea:** https://chef-wise-three.vercel.app
📄 **Documentación:** [`docs/chefwise_documentacion.pdf`](docs/chefwise_documentacion.pdf) · **Presentación:** [`docs/chefwise_presentacion.pdf`](docs/chefwise_presentacion.pdf) · **Estrategia:** [`docs/chefwise_estrategia.pdf`](docs/chefwise_estrategia.pdf)

ChefWise te ayuda a decidir qué cocinar. Recomienda recetas de un catálogo de **28 798 recetas en español**
(México, España y otros países) según lo que se te antoja o lo que tienes en casa, respeta tus alergias, aprende
de las recetas que abres, guardas y cocinas, y te acompaña mientras cocinas con un asistente de IA.

Trabajo final del Diplomado en Ciencia de Datos (generación 34), de principio a fin: web scraping, limpieza,
EDA, ingeniería de variables, dos modelos de recomendación con evaluación offline, una API REST y una app web.

![Inicio de ChefWise](docs/images/home.png)

## Lo más destacado

- **Obtención y limpieza de datos:** scraping de ~9 000 recetas de Kiwilimon (Playwright + BeautifulSoup) unidas
  al dataset RecetasDeLaAbuela de Hugging Face. Se repararon letras rotas, filas mal formadas, duplicados,
  columnas mal nombradas y marcas comerciales, y se normalizaron tiempos, valoraciones y dificultad.
- **Recomendador por contenido:** TF-IDF sobre nombre, ingredientes, etiquetas y país, ordenado por similitud
  coseno más un pequeño peso de calidad (rating bayesiano). Los filtros duros (dificultad, tiempo, país,
  alergias) siempre se respetan y solo se relajan si quedan muy pocas recetas.
- **Comparación de modelos:** embeddings de sentence-transformers contra el baseline TF-IDF en un conjunto de
  evaluación congelado de 320 preguntas, con Precision, Recall, Hit Rate y NDCG@K e intervalos de confianza por
  bootstrap pareado.
- **Personalización:** un perfil de gusto (centroide ponderado de favoritas, cocinadas, guardadas y vistas) que se
  mezcla con la similitud de la consulta.
- **Asistente de IA con herramientas:** *function calling* de Gemini con herramientas tipadas para escalar
  porciones, convertir unidades, sustituir ingredientes, seguridad alimentaria (USDA FSIS) y búsqueda en el
  catálogo. Los cálculos los hace el código, no el modelo, y la respuesta se sanea antes de mostrarla.
- **Ingeniería:** backend FastAPI con contratos Pydantic, frontend Angular, 136 tests de backend (pytest),
  40 tests de frontend (Vitest), CI con GitHub Actions y despliegue serverless en Vercel.

## Resultados

**¿Qué modelo recomienda mejor?** Los dos se calificaron con las mismas 320 preguntas (10 por cada uno de 32
tipos de plato). Una recomendación cuenta como acierto si es el mismo tipo de plato.

| Prueba | Métrica | TF-IDF | Embeddings | IC 95 % de la diferencia | Veredicto |
|---|---|---|---|---|---|
| A: "me gustó esta receta, ¿qué más hay parecido?" | Precision@10 | 0.475 | **0.552** | [+0.048, +0.106] | Embeddings mejor |
| | NDCG@10 | 0.492 | **0.576** | [+0.056, +0.113] | Embeddings mejor |
| | HitRate@5 | 0.850 | **0.919** | [+0.025, +0.116] | Embeddings mejor |
| B: "tengo estos ingredientes, ¿qué cocino?" | NDCG@10 | **0.241** | 0.237 | [−0.026, +0.017] | Sin diferencia clara |
| | HitRate@5 | **0.581** | 0.531 | [−0.106, +0.006] | Sin diferencia clara |

Recomendar al azar da HitRate@5 = 0.05, así que los dos modelos están muy por encima del azar.

**Decisión.** Los embeddings ganan cuando la consulta es una receta completa; con ingredientes literales TF-IDF
rinde igual, ocupa 7 veces menos (6 MB contra 44 MB más un modelo de 488 MB) y no necesita librerías de deep
learning. Por eso la app usa **TF-IDF en "Con lo que tengo" y en el buscador**, y **embeddings en "Sorpréndeme"
cuando están disponibles**; en el despliegue serverless usa TF-IDF. Detalles en
[`notebooks/05_comparacion_baseline_vs_embeddings.ipynb`](notebooks/05_comparacion_baseline_vs_embeddings.ipynb).

## La app

| Sección | Qué puedes hacer |
|---|---|
| **Sorpréndeme** | Eliges categorías (desayuno, postre, pollo, vegetariana, sopa…), nivel (fácil, intermedio, reto), país y tiempo disponible. Te propone recetas que aún no has probado; con "Mostrar ideas nuevas" te da otras sin repetir. |
| **Con lo que tengo** | Escribes los ingredientes que hay en tu cocina y te sugiere qué preparar, ordenado por cuántos de tus ingredientes usa cada receta. Puedes pedir primero las que necesitan menos ingredientes extra. |
| **Buscador** | Busca por nombre de receta o ingrediente en todo el catálogo. |
| **Receta** | Ingredientes, pasos de una sola instrucción y un aviso si lleva algo de lo que marcaste como alergia. Botón "Cociné esto" para llevar tu historial. |
| **Mi cocina** | Resumen del mes, historial, favoritas, guardadas para después, alergias e ingredientes que quieres evitar. |
| **Asistente ChefWise** | Chat flotante que responde sobre la receta abierta o las que ves en pantalla. No inventa recetas ni valores nutricionales. |

![Con lo que tengo](docs/images/with_what_i_have.png)

![Detalle de receta](docs/images/recipe.png)

## Arquitectura

```
Angular (frontend/) ──HTTP──▶ FastAPI (backend/) ──▶ src/ (recomendador)
                                   │                    ├─ data/processed/*.csv    recetas
                                   │                    └─ models/recetas_modelo/  TF-IDF entrenado y embeddings
                                   └──▶ Gemini (solo el asistente, con herramientas en backend/assistant/)
```

Favoritas, historial y alergias se guardan en el `localStorage` del navegador; no hay cuentas ni base de datos.

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `notebooks/` | 01 EDA inicial y limpieza · 02 EDA e ingeniería de variables · 03 recomendador TF-IDF · 04 recomendador con embeddings · 05 comparación de modelos · 06 clusterización K-Means |
| `src/` | Paquete del recomendador: carga de datos, filtros, ranking, perfil de personalización, embeddings y métricas de evaluación. |
| `src/web_scraping/` | Scraping de Kiwilimon (`lista.py` saca las URLs del sitemap y `recetas.py` descarga cada receta). |
| `backend/` | API FastAPI (`main.py`, `routes.py`, `schemas.py`, `settings.py`) y el asistente (`assistant/`). |
| `frontend/` | App Angular. |
| `api/index.py` | Entrada serverless de Vercel (sirve `backend/` bajo `/api`). |
| `data/processed/` | Recetas limpias (`recetas_limpias.csv`) y variables del modelo (`recetas_modelo.csv`). |
| `data/evaluation/` | Conjunto de evaluación congelado y resultados de la comparación. |
| `models/recetas_modelo/` | Vectorizador y matriz TF-IDF, embeddings de las recetas. |
| `tests/` | Tests del backend con los datos y modelos reales. |
| `docs/` | Documentación, presentación, estrategia y capturas. |

## Ejecutar en local

Necesitas Python 3.13 y Node 24+. Desde la raíz del repo:

```bash
# 1. Backend → http://localhost:8000 (docs en /docs)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload

# 2. Frontend → http://localhost:4200 (en otra terminal)
cd frontend && npm install && npm start
```

**Asistente.** Usa Gemini y necesita una clave gratuita: copia `.env.example` como `.env` y pega tu clave de
[Google AI Studio](https://aistudio.google.com/apikey). Reinicia el backend después (el `.env` se lee al arrancar).
Sin clave el chat responde `503` y el resto de la app funciona. Variables opcionales:

| Variable | Por defecto |
|---|---|
| `CHEFWISE_LLM_MODEL` | `gemini-flash-lite-latest` |
| `CHEFWISE_LLM_TIMEOUT` | `30` (segundos) |
| `CHEFWISE_CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` |
| `CHEFWISE_USE_EMBEDDINGS` | `1` (usa embeddings en "Sorpréndeme" si se pueden cargar) |

## Tests

```bash
python -m pytest -q                               # backend
cd frontend && npm test -- --watch=false          # frontend

# Evaluación del asistente con la IA real (opcional; gasta cuota: ~25 peticiones)
CHEFWISE_LIVE_LLM=1 python -m pytest tests/test_chefwise_live.py -v -s
```

## Desplegar en Vercel

1. Importa el repo en [vercel.com/new](https://vercel.com/new). `vercel.json` ya define el frontend y el backend
   (la API queda en `/api`, mismo dominio, sin CORS).
2. En *Settings → Environment Variables* añade `GEMINI_API_KEY`. Sin ella todo funciona menos el chat.
3. Despliega. Con la CLI: `npm i -g vercel && vercel --prod`.

## Regenerar los datos

Solo hace falta para rehacer los CSV y los modelos desde cero (`pip install -r requirements-dev.txt`):

```
scraping ─▶ datos crudos ─▶ notebook 01 ─▶ recetas_limpias.csv ─▶ notebook 02 ─▶ recetas_modelo.csv ─▶ notebook 03 ─▶ models/
```

Los datos crudos no están en el repo. Van en `data/raw/`:

| Archivo | Origen |
|---|---|
| `recetasdelaabuela.csv` | Dataset [somosnlp/RecetasDeLaAbuela](https://huggingface.co/datasets/somosnlp/RecetasDeLaAbuela) de Hugging Face. |
| `recetas_kiwilimon.csv` | Salida del scraping: `python src/web_scraping/lista.py` crea `lista_recetas.txt` y `python src/web_scraping/recetas.py` crea `dataset_recetas.csv` (renómbralo). Antes: `playwright install chromium`. |

Los notebooks 04 a 06 son experimentos y no modifican los datos que usa la app. El modelo
(`models/recetas_modelo/*.joblib`) se guardó con scikit-learn 1.9; al arrancar, el backend comprueba que
corresponde al CSV y, si no, explica el motivo.

## API

| Método y ruta | Descripción |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `POST /recommendations` | "Sorpréndeme": top-N según etiquetas, dificultad, tiempo y país. |
| `POST /recommendations/by-ingredients` | "Con lo que tengo": similitud con los ingredientes escritos. |
| `GET /recipes/{recipe_id}` | Receta completa (404 si no existe). |
| `POST /chat` | Asistente ChefWise sobre las recetas en pantalla (503 sin clave de Gemini). |

Con la API en marcha, `http://localhost:8000/docs` documenta todos los campos.

## Autora

**Itzel Guadalupe Camacho Gómez** · [GitHub](https://github.com/lezti02)
