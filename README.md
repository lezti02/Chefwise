# ChefWise

Recomendador de recetas en español. Un backend FastAPI recomienda con **TF-IDF + similitud coseno** sobre ~28 800 recetas, un frontend Angular lo muestra y un asistente de cocina (Gemini) responde dudas sobre las recetas en pantalla.

```
Angular (frontend/) ──HTTP──▶ FastAPI (backend/) ──▶ src/ (recomendador)
                                                        ├─ data/processed/*.csv   recetas
                                                        └─ models/recetas_modelo/ modelo TF-IDF ya entrenado
```

Todo lo necesario para ejecutar la app ya está en el repo (CSV procesados y modelo entrenado). Los **datos crudos no están**: viven en Google Drive y solo hacen falta si quieres regenerar los datos (ver [Regenerar los datos](#regenerar-los-datos)).

## Estructura

| Ruta | Contenido |
|---|---|
| `frontend/` | App Angular. |
| `backend/` | API FastAPI (`main.py`, `routes.py`, `schemas.py`, `settings.py`) y el asistente ChefWise (`assistant/`). |
| `api/index.py` | Entrada serverless de Vercel (envuelve `backend/` bajo `/api`). |
| `src/` | Lógica del recomendador (filtros, ranking, carga de datos y modelo). `embeddings.py` y `evaluation.py` solo los usan los notebooks 04-05. |
| `src/web_scraping/` | Scraping de Kiwilimon: `lista.py` (URLs desde el sitemap) y `recetas.py` (descarga cada receta). |
| `data/processed/` | `recetas_limpias.csv` (lo que se muestra) y `recetas_modelo.csv` (columnas del modelo). |
| `models/recetas_modelo/` | `tfidf_vectorizer.joblib` y `recipe_tfidf_matrix.joblib` (los usa la app). `recipe_embeddings.npy` y `embedding_metadata.json` son solo del experimento 04-05. |
| `data/evaluation/` | Conjunto de evaluación congelado (`eval_set.json`) y resultados de la comparación TF-IDF vs embeddings. |
| `notebooks/` | 6 notebooks: generan los datos y el modelo (01-03) y experimentos (04-06). Ver abajo. |
| `vercel.json` | Configuración de despliegue. |

## Ejecutar en local

Necesitas Python 3.13 y Node 22+. Desde la raíz del repo:

**1. Backend** → http://localhost:8000 (docs en `/docs`)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

**2. Frontend** → http://localhost:4200 (en otra terminal)

```bash
cd frontend
npm install
npm start
```

`npm start` usa `frontend/src/environments/environment.development.ts` (`apiUrl: http://localhost:8000`).

**3. Chat (asistente ChefWise).** El chat usa Gemini y necesita una clave gratuita:

1. Crea la clave en [Google AI Studio](https://aistudio.google.com/apikey).
2. En la **raíz del repo** (junto a `README.md`) crea un archivo llamado `.env` con esta línea:

   ```
   GEMINI_API_KEY=pega_aqui_tu_clave
   ```

3. Reinicia el backend (`uvicorn ...`): el `.env` se lee solo al arrancar.

`.env` está en `.gitignore`, así que tu clave no se sube a GitHub.

Sin clave, el chat responde `503` y el resto de la app funciona. Otras variables opcionales:

| Variable | Por defecto |
|---|---|
| `CHEFWISE_LLM_MODEL` | `gemini-flash-lite-latest` |
| `CHEFWISE_LLM_TIMEOUT` | `30` (segundos) |
| `CHEFWISE_CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` |

## Desplegar en Vercel

1. Sube este repo a GitHub e impórtalo en [vercel.com/new](https://vercel.com/new). No cambies nada: `vercel.json` ya define el build del frontend (`frontend/dist/chefwise/browser`) y la función Python `api/index.py`.
2. En *Settings → Environment Variables* añade `GEMINI_API_KEY` con tu clave (el `.env` local no se despliega). Sin ella todo funciona menos el chat. Si la añades después de desplegar, haz *Redeploy*.
3. Despliega. El frontend y la API quedan en el mismo dominio (la API en `/api`), por eso no hace falta CORS.

Con la CLI: `npm i -g vercel && vercel --prod`.

## Regenerar los datos

Solo si quieres rehacer los CSV y el modelo desde cero. Cadena completa:

```
scraping ─▶ datos crudos (Drive) ─▶ notebook 01 ─▶ recetas_limpias.csv ─▶ notebook 02 ─▶ recetas_modelo.csv ─▶ notebook 03 ─▶ models/
```

**Datos crudos.** Sube estos dos archivos a una carpeta de tu Google Drive (por defecto `Mi unidad/chefWise/raw/`):

| Archivo | Origen |
|---|---|
| `recetasdelaabuela.csv` | Dataset [somosnlp/RecetasDeLaAbuela](https://huggingface.co/datasets/somosnlp/RecetasDeLaAbuela) de Hugging Face. |
| `recetas_kiwilimon.csv` | Salida del scraping: `python src/web_scraping/lista.py` crea `lista_recetas.txt` y `python src/web_scraping/recetas.py` crea `dataset_recetas.csv` (renómbralo). Necesita `pip install -r requirements-dev.txt` y `playwright install chromium`. |

**Notebooks** (`pip install -r requirements-dev.txt` y `jupyter lab`):

| Notebook | Entrada | Salida |
|---|---|---|
| `01_limpieza_datos.ipynb` | los dos CSV crudos | `data/processed/recetas_limpias.csv` |
| `02_variables_del_modelo.ipynb` | `recetas_limpias.csv` | `data/processed/recetas_modelo.csv` |
| `03_modelo_tfidf.ipynb` | `recetas_modelo.csv` | `models/recetas_modelo/*.joblib` |
| `04_recomendador_embeddings.ipynb` | `recetas_modelo.csv` | `recipe_embeddings.npy` (descarga el modelo de Hugging Face la primera vez) |
| `05_comparacion_baseline_vs_embeddings.ipynb` | `eval_set.json`, modelos 03 y 04 | métricas en `data/evaluation/` |
| `06_clusterizacion_kmeans.ipynb` | `recetas_modelo.csv` | análisis de K-Means (no cambia ningún archivo) |

Los notebooks 04-06 son experimentos: **la app no los usa** y siempre recomienda con el TF-IDF del 03.

El notebook 01 es el único que lee datos crudos y los busca así:

* **Google Colab:** monta tu Drive y lee de `MyDrive/chefWise/raw` (cambia `DRIVE_RAW_FOLDER` en la primera celda si usaste otra carpeta). El CSV limpio se guarda en `/content/chefWise_out/`: descárgalo y ponlo en `data/processed/` del repo.
* **Local:** lee de `data/raw/` (ignorada por git) o de la carpeta indicada en la variable de entorno `CHEFWISE_RAW_DIR` (por ejemplo, la de Google Drive para escritorio).

Los notebooks 02 y 03 se ejecutan dentro del repo (importan `src/`). Tras regenerar el modelo, el backend comprueba al arrancar que los `.joblib` corresponden al CSV y, si no, explica el motivo.

## API

| Método y ruta | Descripción |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `POST /recommendations` | "Sorpréndeme": top-N según antojos, dificultad, tiempo y país. |
| `POST /recommendations/by-ingredients` | "Con lo que tengo": similitud con los ingredientes escritos. |
| `GET /recipes/{recipe_id}` | Receta completa (404 si no existe). |
| `POST /chat` | Asistente ChefWise sobre las recetas en pantalla (503 sin clave de Gemini). |

Ejemplo de `POST /recommendations`:

```json
{"antojos": ["rapido"], "difficulty": "facil", "max_time": 30, "countries": [], "exclude_ids": [], "top_n": 12}
```

* `antojos`: `rapido | saludable | reconfortante | dulce | picante | ligero` (se traducen a filtros y palabras de búsqueda en `src/preferences.py`).
* `difficulty`: `facil | intermedio | reto`. `max_time`: minutos. `countries`: vacío = cualquiera. `exclude_ids`: recetas que no deben salir.
* El ranking es `similitud coseno + 0.05 × calidad` (rating bayesiano).

Con la API en marcha, `http://localhost:8000/docs` documenta todos los campos.

## Notas

* Favoritas, historial, alergias y recetas ocultas se guardan en el `localStorage` del navegador (no hay base de datos).
* Los `.joblib` se guardaron con scikit-learn 1.9.x; `requirements.txt` fija una versión compatible.
