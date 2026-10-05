import { Injectable, signal } from '@angular/core';
import { Difficulty, Recipe } from '../models/recipe.model';

export type KitchenTab = 'resumen' | 'historial' | 'favoritas' | 'quiero' | 'preferencias';

/**
 * Lo que cada pantalla tenía en pantalla (recetas mostradas, filtros elegidos,
 * texto escrito) para recuperarlo al volver con "Regresar" desde una receta o
 * desde otra sección. Vive solo mientras la pestaña está abierta; al recargar
 * la página se parte de cero.
 *
 * Los componentes se destruyen al navegar, por eso su estado no puede vivir en
 * ellos: aquí cada página guarda sus signals y los vuelve a leer al crearse.
 */
@Injectable({ providedIn: 'root' })
export class ViewStateService {
  readonly home = {
    searchTerm: signal(''),
    /** Texto con el que se hizo la búsqueda que muestran los resultados (puede diferir de lo escrito). */
    committedQuery: signal(''),
    active: signal(false),
    /** Todo lo recibido del backend hasta ahora, sin filtrar. */
    results: signal<Recipe[]>([]),
    total: signal(0),
    hasMore: signal(false),
  };

  readonly surprise = {
    selectedTags: signal<string[]>([]),
    difficulty: signal<Difficulty>('facil'),
    country: signal<string | null>(null),
    maxMinutes: signal(30),
    /** true = sin límite de tiempo de preparación (se ignora `maxMinutes`). */
    anyTime: signal(false),
    suggestions: signal<Recipe[]>([]),
    /** Para que aplicar los mismos filtros no repita las recetas ya mostradas. */
    shown: { queryKey: '', ids: new Set<string>() },
  };

  readonly haveIngredients = {
    ingredients: signal<string[]>([]),
    fewestExtras: signal(true),
    /** Todo lo mostrado hasta ahora (cada "buscar más" agrega al final). */
    results: signal<Recipe[]>([]),
    searched: signal(false),
    /** Ingredientes y orden con los que se obtuvieron `results` (lo escrito después no los cambia). */
    searchedWith: signal<{ ingredients: string[]; fewestExtras: boolean } | null>(null),
    nextOffset: signal(0),
    hasMore: signal(false),
    total: signal(0),
    ingredientsTotal: signal(0),
    bestMatchCount: signal(0),
  };

  readonly kitchenTab = signal<KitchenTab>('resumen');
}
