# ChefWise

🌐 **Pruébalo en línea: https://chef-wise-three.vercel.app**

ChefWise es una aplicación web que te ayuda a decidir qué cocinar. Tiene un catálogo de unas 28 800 recetas en español (México, España y otros países), te recomienda según lo que te apetece o lo que tienes en casa, respeta tus alergias y te acompaña mientras cocinas con un asistente de IA.

## Qué hace

| Sección | Qué puedes hacer |
|---|---|
| **Sorpréndeme** | Eliges lo que encaja con el momento: categorías (desayuno, postre, pollo, vegetariana, sopa…), nivel de experiencia (fácil, intermedio, reto), país y tiempo disponible. Te propone recetas que aún no has probado; con "Mostrar ideas nuevas" te da otras sin repetir. |
| **Con lo que tengo** | Escribes los ingredientes que hay en tu cocina y te sugiere qué preparar, ordenado por cuántos de tus ingredientes usa cada receta. Puedes pedir primero las que necesitan menos ingredientes extra. |
| **Buscador** | Busca por nombre de receta o ingrediente en todo el catálogo desde la página de inicio. |
| **Receta** | Ingredientes, pasos de una sola instrucción y un aviso si lleva algo de lo que marcaste como alergia. Botón "Cociné esto" para llevar tu historial. |
| **Mi cocina** | Resumen del mes, historial, favoritas, recetas guardadas para después y tus preferencias: alergias e ingredientes que quieres evitar (no se te recomendarán, o se te avisará en cada receta si decides verlas). |
| **ChefWise, el asistente** | Un chat flotante (IA de Gemini) que responde sobre la receta que tienes abierta o las que ves en pantalla: sustituciones de ingredientes, conversión de unidades, escalar porciones, seguridad alimentaria, qué te falta de una receta según lo que tienes y búsqueda en el catálogo. No inventa recetas ni valores nutricionales. |

Tus favoritas, historial y alergias se guardan en tu navegador (no hay cuentas ni base de datos).

## Cómo funciona

```
Angular (frontend/) ──HTTP──▶ FastAPI (backend/) ──▶ src/ (recomendador)
                                   │                    ├─ data/processed/*.csv   recetas
                                   │                    └─ models/recetas_modelo/ modelo TF-IDF ya entrenado
                                   └──▶ Gemini (solo el chat)
```

1. **Datos.** Las recetas vienen de dos fuentes ([RecetasDeLaAbuela](https://huggingface.co/datasets/somosnlp/RecetasDeLaAbuela) y Kiwilimon, esta última obtenida con scraping). Los notebooks 01 y 02 las limpian (letras rotas, marcas comerciales, promoción, duplicados, pasos largos), les asignan etiquetas y calculan variables como los ingredientes base, el esfuerzo y el tiempo.
2. **Modelo.** Cada receta se convierte en un texto (nombre + ingredientes + etiquetas + país) y se representa con **TF-IDF**: las palabras raras pesan más que las comunes (`chipotle` dice más de un plato que `sal`). Dos recetas, o una receta y lo que tú escribes, se parecen según su **similitud coseno**. El modelo se entrena una vez (notebook 03) y se guarda en `models/`.
3. **Recomendar.** Primero se aplican los filtros duros (dificultad, tiempo, país, alergias, recetas ya mostradas). Después se ordena por similitud con tu consulta, con un pequeño peso extra para las recetas bien valoradas. Si los filtros dejan muy pocas recetas, se relajan y la respuesta lo indica. En "Con lo que tengo" la consulta son tus ingredientes.
4. **Asistente.** El backend envía a Gemini tu pregunta junto con la receta abierta y herramientas propias (escalado, conversión de unidades, sustituciones, seguridad alimentaria, búsqueda). Los cálculos los hace el código, no el modelo, y la respuesta se sanea antes de mostrarla.

Todo lo necesario para ejecutar la app ya está en el repo (CSV procesados y modelo entrenado). Los **datos crudos no están**: se descargan de Google Drive y solo hacen falta si quieres regenerar los datos (ver [Regenerar los datos](#regenerar-los-datos)).

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

1. Sube este repo a GitHub e impórtalo en [vercel.com/new](https://vercel.com/new). No cambies nada: `vercel.json` ya define ambos servicios.
2. En *Settings → Environment Variables* añade `GEMINI_API_KEY` con tu clave (el `.env` local no se despliega). Sin ella todo funciona menos el chat. Si la añades después de desplegar, haz *Redeploy*.
3. Despliega. `vercel.json` usa *Vercel Services*: el frontend Angular (`frontend/`) y el backend FastAPI (`api/index.py`) se despliegan juntos y comparten dominio (la API en `/api`), por eso no hace falta CORS.

Con la CLI: `npm i -g vercel && vercel --prod`.

## Regenerar los datos

Solo si quieres rehacer los CSV y el modelo desde cero. Cadena completa:

```
scraping ─▶ datos crudos (Drive) ─▶ notebook 01 ─▶ recetas_limpias.csv ─▶ notebook 02 ─▶ recetas_modelo.csv ─▶ notebook 03 ─▶ models/
```

**Datos crudos.** No están en el repo: viven en Google Drive. Son estos dos archivos:

| Archivo | Origen |
|---|---|
| `recetasdelaabuela.csv` | Dataset [somosnlp/RecetasDeLaAbuela](https://huggingface.co/datasets/somosnlp/RecetasDeLaAbuela) de Hugging Face. |
| `recetas_kiwilimon.csv` | Salida del scraping: `python src/web_scraping/lista.py` crea `lista_recetas.txt` y `python src/web_scraping/recetas.py` crea `dataset_recetas.csv` (renómbralo). Necesita `pip install -r requirements-dev.txt` y `playwright install chromium`. |

El notebook 01 los descarga solos con `gdown` (sin iniciar sesión ni montar Drive), así que funciona desde cualquier cuenta de Colab. Los enlaces están en `DRIVE_FILE_IDS`, en la primera celda del notebook; si subes otra versión de los archivos, pega ahí su nuevo ID (la parte central de `https://drive.google.com/file/d/<ID>/view`).

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

### Cómo ejecutarlos en Google Colab

Abre el notebook en Colab (*Archivo → Abrir cuaderno → GitHub* y pega la URL del repo) y ejecútalo de arriba abajo. Todos empiezan con una celda de preparación que, en Colab, clona el repo, instala las dependencias con las versiones del proyecto y entra en la carpeta del repo; en local no hace nada.

* **Cada notebook funciona por separado.** Colab abre cada uno en una máquina distinta, así que el 02 no ve la salida del 01 de otra sesión: parte del CSV que ya está en el repo (`recetas_limpias.csv`), y el 03 parte de `recetas_modelo.csv`.
* **El 01 es el único que lee datos crudos.** Los descarga de Drive a una carpeta temporal (nunca dentro del repo) y escribe `data/processed/recetas_limpias.csv`.
* **Para encadenar resultados nuevos** (por ejemplo, tras re-limpiar con el 01): descarga el CSV generado desde el panel de archivos de Colab, súbelo a `data/processed/` del repo (o a la sesión del siguiente notebook) y continúa con el 02 y el 03. Los archivos de una sesión de Colab se pierden al cerrarla, así que descarga lo que quieras conservar y haz commit.
* **Local:** los mismos notebooks (`jupyter lab` desde la raíz del repo), sin la preparación.

El modelo (`models/recetas_modelo/*.joblib`) debe generarse con las versiones de `requirements.txt` (scikit-learn 1.9.x); por eso la celda de preparación las instala en Colab. Tras regenerar el modelo, el backend comprueba al arrancar que los `.joblib` corresponden al CSV y, si no, explica el motivo.

## API

| Método y ruta | Descripción |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `POST /recommendations` | "Sorpréndeme": top-N según etiquetas, dificultad, tiempo y país. |
| `POST /recommendations/by-ingredients` | "Con lo que tengo": similitud con los ingredientes escritos. |
| `GET /recipes/{recipe_id}` | Receta completa (404 si no existe). |
| `POST /chat` | Asistente ChefWise sobre las recetas en pantalla (503 sin clave de Gemini). |

Ejemplo de `POST /recommendations`:

```json
{"tags": ["Pollo"], "difficulty": "facil", "max_time": 30, "countries": [], "exclude_ids": [], "top_n": 12}
```

* `tags`: etiquetas exactas del dataset (`Desayuno`, `Comida`, `Cena`, `Postre`, `Bebida`, `Alcohol`, `Vegetariana`, `Vegana`, `Cerdo`, `Pollo`, `Mariscos`, `Res`, `Pavo`, `Cordero`, `Pasta`, `Sopa`). Si no hay suficientes recetas con todas, el backend relaja el filtro.
* `difficulty`: `facil | intermedio | reto`. `max_time`: minutos. `countries`: vacío = cualquiera. `exclude_ids`: recetas que no deben salir.
* El ranking es similitud coseno (TF-IDF) con un pequeño peso de calidad (rating bayesiano).

Con la API en marcha, `http://localhost:8000/docs` documenta todos los campos.

## Notas

* Favoritas, historial, alergias y recetas ocultas se guardan en el `localStorage` del navegador (no hay base de datos).
* Los `.joblib` se guardaron con scikit-learn 1.9.x; `requirements.txt` fija una versión compatible.
