import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { EMPTY, Observable, expand, last, map, tap } from 'rxjs';
import { MetadataDto } from '../models/api.model';
import { Allergen, COMMON_ALLERGENS, Difficulty, MealCategory, Recipe, RecipePage } from '../models/recipe.model';
import { RecipeApiService } from './recipe-api.service';

const HIDDEN_KEY = 'chefwise.hiddenRecipes';
const ALLERGIES_KEY = 'chefwise.allergies';
const ALLOW_ALLERGENS_KEY = 'chefwise.allowAllergenRecipes';
const STATE_KEY = 'chefwise.recipeState';
const SNAPSHOTS_KEY = 'chefwise.recipeSnapshots';

/** Cuántas ideas se muestran en Sorpréndeme / Con lo que tengo. */
const RESULTS_COUNT = 5;
/** Con alergias activas se piden más candidatos, porque parte se descarta en el cliente. */
const RESULTS_COUNT_WITH_ALLERGIES = 40;
/** Páginas extra que se piden como máximo cuando las alergias descartan lo recibido. */
const MAX_FILL_REQUESTS = 8;

export interface AllergyPrefs {
  /** ids de COMMON_ALLERGENS */
  presets: string[];
  /** ingredientes escritos por el usuario, ej. "cilantro" */
  custom: string[];
}

/** Lo que el usuario ha hecho con una receta (no viene del dataset). */
interface UserRecipeState {
  isFavorite: boolean;
  isSaved: boolean;
  lastCookedAt: string | null;
}

export interface IngredientsQuery {
  ingredients: string[];
  /** Ordena primero lo que aprovecha más ingredientes con menos extras. */
  fewestExtras: boolean;
  /** Cuántos resultados del backend ya se consumieron (para "buscar más"). */
  offset: number;
}

/** Página de "Con lo que tengo": recetas ya filtradas para el usuario + dónde seguir. */
export interface IngredientsPage extends RecipePage {
  /** Valor de `offset` para pedir la siguiente página. */
  nextOffset: number;
}

export interface SurpriseQuery {
  /** Valores exactos de `tags` devueltos por GET /metadata. */
  tags: string[];
  difficulty: Difficulty | null;
  maxMinutes: number | null;
  country: string | null;
  /** ids adicionales a omitir (ej. lo que ya se mostró en esta sesión). */
  extraExcludeIds?: string[];
}

@Injectable({ providedIn: 'root' })
export class RecipeService {
  private api = inject(RecipeApiService);

  /**
   * Las recetas YA NO viven aquí: se piden al backend (que lee el dataset real).
   * Este servicio conserva solo lo que es del usuario y todavía no tiene base
   * de datos: favoritas, guardadas, historial, alergias y recetas ocultas.
   *
   * Se guardan en localStorage junto con una "foto" ligera de cada receta, para
   * poder pintar Favoritas / Historial / Ocultas sin volver a pedirlas.
   *
   * TODO backend (etapa con base de datos): mover todo esto a /users/me/... y
   * registrar cada acción como interacción para el recomendador.
   */
  private readonly _state = signal<Record<string, UserRecipeState>>(load(STATE_KEY, {}));
  private readonly _snapshots = signal<Record<string, Recipe>>(load(SNAPSHOTS_KEY, {}));
  private readonly _hiddenIds = signal<string[]>(load<string[]>(HIDDEN_KEY, []).filter(isRecipeId));
  readonly hiddenIds = this._hiddenIds.asReadonly();

  /** Recetas que el backend entregó en esta sesión (para poder guardar su "foto" al interactuar). */
  private readonly seen = new Map<string, Recipe>();

  readonly hiddenRecipes = computed(() =>
    this._hiddenIds()
      .map(id => this._snapshots()[id])
      .filter((r): r is Recipe => !!r)
      .map(r => this.decorate(r))
  );

  /** Última receta ocultada, para el aviso de "Deshacer". */
  readonly lastHidden = signal<Recipe | null>(null);
  private lastHiddenTimer?: ReturnType<typeof setTimeout>;

  private readonly _allergies = signal<AllergyPrefs>(load(ALLERGIES_KEY, { presets: [], custom: [] }));
  readonly allergies = this._allergies.asReadonly();
  readonly commonAllergens = COMMON_ALLERGENS;

  /**
   * true = las recetas con tus alérgenos también aparecen en las recomendaciones; cada tarjeta
   * avisa "Contiene: …". Por defecto (false) se descartan.
   */
  private readonly _allowAllergenRecipes = signal<boolean>(load(ALLOW_ALLERGENS_KEY, false));
  readonly allowAllergenRecipes = this._allowAllergenRecipes.asReadonly();

  /** Alérgenos activos ya convertidos a reglas de búsqueda (preset + personalizados). */
  private readonly activeAllergenRules = computed<Allergen[]>(() => {
    const { presets, custom } = this._allergies();
    return [
      ...COMMON_ALLERGENS.filter(a => presets.includes(a.id)),
      ...custom.map(term => ({ id: `custom:${term}`, label: term, keywords: [normalize(term)] })),
    ];
  });
  readonly activeAllergyLabels = computed(() => this.activeAllergenRules().map(a => a.label));

  constructor() {
    effect(() => save(HIDDEN_KEY, this._hiddenIds()));
    effect(() => save(ALLERGIES_KEY, this._allergies()));
    effect(() => save(ALLOW_ALLERGENS_KEY, this._allowAllergenRecipes()));
    effect(() => save(STATE_KEY, this._state()));
    effect(() => save(SNAPSHOTS_KEY, this._snapshots()));
  }

  private readonly withState = (predicate: (s: UserRecipeState) => boolean): Recipe[] =>
    Object.entries(this._state())
      .filter(([, s]) => predicate(s))
      .map(([id]) => this._snapshots()[id])
      .filter((r): r is Recipe => !!r)
      .map(r => this.decorate(r));

  readonly favorites = computed(() => this.withState(s => s.isFavorite));
  readonly saved = computed(() => this.withState(s => s.isSaved));

  /** Recetas cocinadas, más recientes primero — alimenta el historial de "Mi cocina". */
  readonly history = computed(() =>
    this.withState(s => !!s.lastCookedAt).sort((a, b) => (b.lastCookedAt! > a.lastCookedAt! ? 1 : -1))
  );

  /**
   * Distribución de categorías entre lo cocinado (para la pestaña "Resumen").
   * Cálculo simple en el cliente; las recetas sin `app_category` en el dataset
   * no se cuentan. En producción esto se calcula en el backend.
   */
  readonly categoryStats = computed(() => {
    const cooked = this.history().filter(r => r.category);
    const total = cooked.length || 1;
    const counts: Record<MealCategory, number> = { desayuno: 0, comida: 0, cena: 0, postre: 0, bebida: 0 };
    cooked.forEach(r => counts[r.category!]++);
    return (Object.keys(counts) as MealCategory[])
      .map(category => ({ category, percent: Math.round((counts[category] / total) * 100) }))
      .filter(c => c.percent > 0);
  });

  // ---------- Recetas (API) ----------

  /** Receta completa (con pasos) desde GET /recipes/{id}. */
  loadRecipe(id: string): Observable<Recipe> {
    return this.api.getRecipe(id).pipe(tap(recipe => this.ingest([recipe])));
  }

  /** Registra recetas recién recibidas del backend. */
  private ingest(recipes: Recipe[]): void {
    for (const r of recipes) this.seen.set(r.id, r);
  }

  /** Superpone el estado del usuario (favorita, guardada, cocinada) a una receta del backend. */
  decorate(recipe: Recipe): Recipe {
    const s = this._state()[recipe.id];
    return {
      ...recipe,
      isFavorite: s?.isFavorite ?? false,
      isSaved: s?.isSaved ?? false,
      lastCookedAt: s?.lastCookedAt ?? null,
      neverCooked: !s?.lastCookedAt,
    };
  }

  toggleFavorite(id: string): void {
    this.updateState(id, s => ({ ...s, isFavorite: !s.isFavorite }));
    // TODO backend: POST /api/recipes/{id}/favorite — señal positiva para el recomendador.
  }

  toggleSaved(id: string): void {
    this.updateState(id, s => ({ ...s, isSaved: !s.isSaved }));
    // TODO backend: POST /api/recipes/{id}/save
  }

  markCooked(id: string): void {
    this.updateState(id, s => ({ ...s, lastCookedAt: new Date().toISOString() }));
    // TODO backend: POST /api/recipes/{id}/cooked
  }

  /** Quita la receta del historial sin alterar si está guardada o es favorita. */
  removeFromHistory(id: string): void {
    this.updateState(id, s => ({ ...s, lastCookedAt: null }));
  }

  private updateState(id: string, updater: (s: UserRecipeState) => UserRecipeState): void {
    const current = this._state()[id] ?? { isFavorite: false, isSaved: false, lastCookedAt: null };
    this._state.update(all => ({ ...all, [id]: updater(current) }));
    this.rememberSnapshot(id);
    this.prune();
  }

  /** Guarda una "foto" ligera (sin pasos) para poder listar la receta después. */
  private rememberSnapshot(id: string): void {
    const recipe = this.seen.get(id);
    if (recipe && !this._snapshots()[id]) {
      this._snapshots.update(all => ({ ...all, [id]: { ...recipe, steps: [] } }));
    }
  }

  /** Quita estado y fotos de recetas que ya no son favoritas/guardadas/cocinadas/ocultas. */
  private prune(): void {
    const state = { ...this._state() };
    for (const [id, s] of Object.entries(state)) {
      if (!s.isFavorite && !s.isSaved && !s.lastCookedAt) delete state[id];
    }
    this._state.set(state);

    const keep = new Set([...Object.keys(state), ...this._hiddenIds()]);
    const snapshots = this._snapshots();
    if (Object.keys(snapshots).some(id => !keep.has(id))) {
      this._snapshots.set(Object.fromEntries(Object.entries(snapshots).filter(([id]) => keep.has(id))));
    }
  }

  // ---------- "No volver a mostrar" ----------

  isHidden(id: string): boolean {
    return this._hiddenIds().includes(id);
  }

  hide(id: string): void {
    if (this.isHidden(id)) return;
    this._hiddenIds.update(ids => [...ids, id]);
    this.rememberSnapshot(id);
    this.lastHidden.set(this.seen.get(id) ?? null);
    clearTimeout(this.lastHiddenTimer);
    this.lastHiddenTimer = setTimeout(() => this.lastHidden.set(null), 6000);
    // TODO backend: POST /api/recipes/{id}/hide
  }

  unhide(id: string): void {
    this._hiddenIds.update(ids => ids.filter(x => x !== id));
    if (this.lastHidden()?.id === id) this.lastHidden.set(null);
    this.prune();
    // TODO backend: DELETE /api/recipes/{id}/hide
  }

  undoLastHide(): void {
    const r = this.lastHidden();
    if (r) this.unhide(r.id);
  }

  dismissLastHidden(): void {
    this.lastHidden.set(null);
  }

  // ---------- Alergias ----------

  togglePresetAllergy(id: string): void {
    this._allergies.update(a => ({
      ...a,
      presets: a.presets.includes(id) ? a.presets.filter(x => x !== id) : [...a.presets, id],
    }));
  }

  addCustomAllergy(term: string): void {
    const value = term.trim().toLowerCase();
    if (!value) return;
    this._allergies.update(a =>
      a.custom.some(c => normalize(c) === normalize(value)) ? a : { ...a, custom: [...a.custom, value] }
    );
  }

  removeCustomAllergy(term: string): void {
    this._allergies.update(a => ({ ...a, custom: a.custom.filter(c => c !== term) }));
  }

  /** Etiquetas de las alergias del usuario presentes en la receta (vacío = segura). */
  allergensIn(recipe: Recipe): string[] {
    const ingredientTexts = recipe.ingredients.map(i => normalize(i.name));
    return this.activeAllergenRules()
      .filter(rule => ingredientTexts.some(text => matchesAllergen(text, rule)))
      .map(rule => rule.label);
  }

  setAllowAllergenRecipes(value: boolean): void {
    this._allowAllergenRecipes.set(value);
  }

  /** Quita recetas ocultas y, salvo que el usuario lo permita, las que llevan sus alérgenos. */
  filterForUser(list: Recipe[]): Recipe[] {
    const keepAllergens = this._allowAllergenRecipes();
    return list.filter(r => !this.isHidden(r.id) && (keepAllergens || this.allergensIn(r).length === 0));
  }

  // ---------- Recomendadores (backend) ----------

  getMetadata(): Observable<MetadataDto> {
    return this.api.getMetadata();
  }

  /** Una página de la búsqueda del catálogo; `offset` = cuántas recetas ya se mostraron. */
  searchCatalog(query: string, tag: string | null, offset = 0): Observable<RecipePage> {
    return this.api.searchRecipes(query, tag, RESULTS_COUNT, offset).pipe(
      map(page => ({ ...page, recipes: page.recipes.map(r => this.decorate(r)) })),
      tap(page => this.ingest(page.recipes))
    );
  }

  /**
   * "Sorpréndeme": POST /recommendations. Manda los controles tal cual y el
   * backend aplica filtros + TF-IDF/coseno sobre el dataset real.
   *
   * Se excluyen las recetas ocultas y las ya cocinadas (la pantalla promete
   * "algo que aún no has probado"); las alergias se filtran aquí con las reglas
   * de ingredientes de la UI, por eso se piden más candidatos si hay alguna.
   */
  getSurpriseSuggestions(query: SurpriseQuery): Observable<Recipe[]> {
    const hasAllergies = this.activeAllergenRules().length > 0 && !this._allowAllergenRecipes();
    return this.api
      .recommend({
        tags: query.tags,
        difficulty: query.difficulty,
        max_time: query.maxMinutes,
        countries: query.country ? [query.country] : [],
        exclude_ids: this.excludedIds(query.extraExcludeIds),
        top_n: hasAllergies ? RESULTS_COUNT_WITH_ALLERGIES : RESULTS_COUNT,
      })
      .pipe(
        map(list => this.filterForUser(list).slice(0, RESULTS_COUNT)),
        tap(list => this.ingest(list))
      );
  }

  /**
   * "Con lo que tengo": POST /recommendations/by-ingredients. El backend ordena
   * (por similitud TF-IDF, o por aprovechamiento y menos extras si `fewestExtras`)
   * y pagina con `offset`; cada receta llega con los ingredientes del usuario que
   * usa y cuántos extras necesita.
   *
   * Las ocultas y las que llevan alérgenos se descartan aquí, así que si una página
   * queda corta se piden más hasta juntar RESULTS_COUNT o agotar resultados.
   */
  getHaveIngredientsPage(query: IngredientsQuery): Observable<IngredientsPage> {
    const fetchPage = (offset: number, kept: Recipe[]) =>
      this.api
        .recommendByIngredients({
          ingredients: query.ingredients,
          exclude_ids: this.excludedIds(),
          top_n: RESULTS_COUNT,
          offset,
          fewest_extras: query.fewestExtras,
        })
        .pipe(map(page => ({ page, offset, recipes: [...kept, ...this.filterForUser(page.recipes)] })));

    return fetchPage(query.offset, []).pipe(
      expand(step => {
        const filled = step.recipes.length >= RESULTS_COUNT;
        const exhausted = !step.page.hasMore || step.offset - query.offset >= MAX_FILL_REQUESTS * RESULTS_COUNT;
        return filled || exhausted ? EMPTY : fetchPage(step.offset + RESULTS_COUNT, step.recipes);
      }),
      last(),
      map(step => ({ ...step.page, recipes: step.recipes, nextOffset: step.offset + RESULTS_COUNT })),
      tap(page => this.ingest(page.recipes))
    );
  }

  private excludedIds(extra: string[] = []): number[] {
    const cooked = Object.entries(this._state())
      .filter(([, s]) => !!s.lastCookedAt)
      .map(([id]) => id);
    return [...new Set([...this._hiddenIds(), ...cooked, ...extra])].filter(isRecipeId).map(Number);
  }
}

function isRecipeId(id: unknown): id is string {
  return typeof id === 'string' && /^\d+$/.test(id);
}

/** Minúsculas y sin acentos, para comparar "Salmón" con "salmon". */
function normalize(text: string): string {
  return text.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Busca las keywords como palabra completa (admitiendo plural -s/-es), para
 * que "pan" no marque "panela", tras borrar las excepciones del texto.
 */
function matchesAllergen(normalizedText: string, rule: Allergen): boolean {
  let text = normalizedText;
  for (const exc of rule.exceptions ?? []) text = text.split(normalize(exc)).join(' ');
  return rule.keywords.some(kw => new RegExp(`\\b${escapeRegExp(normalize(kw))}(s|es)?\\b`).test(text));
}

function load<T>(key: string, fallback: T): T {
  try {
    const raw = globalThis.localStorage?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown): void {
  try {
    globalThis.localStorage?.setItem(key, JSON.stringify(value));
  } catch {
    /* almacenamiento lleno o bloqueado: las preferencias solo durarán la sesión */
  }
}
