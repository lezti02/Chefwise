import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { ChatService } from '../../services/chat.service';
import { RecipeService } from '../../services/recipe.service';
import { ViewStateService } from '../../services/view-state.service';

@Component({
  selector: 'app-have-ingredients',
  standalone: true,
  imports: [RouterLink, RecipeCardComponent],
  templateUrl: './have-ingredients.component.html',
  styleUrl: './have-ingredients.component.scss',
})
export class HaveIngredientsComponent {
  // Lo escrito, las opciones y las recetas mostradas se conservan al salir y volver (ver ViewStateService).
  private view = inject(ViewStateService).haveIngredients;
  ingredients = this.view.ingredients;
  /** true = ordenar por lo que aprovecha más de lo que tienes con menos extras; false = no importan los extras. */
  fewestExtras = this.view.fewestExtras;
  searched = this.view.searched;
  hasMore = this.view.hasMore;
  total = this.view.total;
  ingredientsTotal = this.view.ingredientsTotal;
  bestMatchCount = this.view.bestMatchCount;

  loading = signal(false);
  loadingMore = signal(false);
  error = signal<string | null>(null);

  visibleResults = computed(() =>
    this.recipeService.filterForUser(this.view.results()).map(r => this.recipeService.decorate(r))
  );

  /** Aviso cuando ninguna receta del catálogo usa todos los ingredientes escritos. */
  coverageNote = computed(() => {
    const total = this.ingredientsTotal();
    const best = this.bestMatchCount();
    if (!this.searched() || !total || best >= total) return null;
    return best === 0
      ? `No encontramos recetas que usen tus ingredientes.`
      : `Ninguna receta usa los ${total} ingredientes a la vez. Lo más que se aprovecha son ${best} de ${total}; ` +
          `en cada receta te indicamos cuáles usa.`;
  });

  private request?: Subscription;

  constructor(public recipeService: RecipeService) {
    inject(DestroyRef).onDestroy(() => this.request?.unsubscribe());
    this.shareWithChat();
  }

  addIngredient(input: HTMLInputElement): void {
    const value = input.value.trim();
    if (value) this.ingredients.update(list => [...list, value]);
    input.value = '';
  }

  addIngredientOnEnter(event: Event, input: HTMLInputElement): void {
    event.preventDefault();
    this.addIngredient(input);
  }

  removeIngredient(index: number): void {
    this.ingredients.update(list => list.filter((_, i) => i !== index));
  }

  /** Permitir/ocultar recetas con tus alergias; si ya se buscó, se repite la búsqueda con el nuevo criterio. */
  setAllowAllergens(value: boolean): void {
    this.recipeService.setAllowAllergenRecipes(value);
    if (this.searched()) this.search();
  }

  setFewestExtras(value: boolean): void {
    this.fewestExtras.set(value);
  }

  /**
   * Busca qué se puede cocinar con los ingredientes escritos
   * (POST /recommendations/by-ingredients).
   */
  search(): void {
    if (!this.ingredients().length) return;
    this.request?.unsubscribe();
    this.loading.set(true);
    this.loadingMore.set(false);
    this.error.set(null);
    const query = { ingredients: [...this.ingredients()], fewestExtras: this.fewestExtras() };
    this.request = this.recipeService.getHaveIngredientsPage({ ...query, offset: 0 }).subscribe({
      next: page => {
        this.view.searchedWith.set(query);
        this.view.results.set(page.recipes);
        this.applyPage(page);
        this.searched.set(true);
        this.loading.set(false);
      },
      error: () => {
        this.view.results.set([]);
        this.searched.set(false);
        this.error.set('No pudimos obtener recetas del servidor. Revisa que el backend esté en marcha e inténtalo de nuevo.');
        this.loading.set(false);
      },
    });
  }

  /** "Buscar más opciones": siguiente tanda de la misma búsqueda, agregada al final. */
  loadMore(): void {
    const query = this.view.searchedWith();
    if (!query || this.loading() || this.loadingMore() || !this.hasMore()) return;
    this.request?.unsubscribe();
    this.loadingMore.set(true);
    this.error.set(null);
    this.request = this.recipeService.getHaveIngredientsPage({ ...query, offset: this.view.nextOffset() }).subscribe({
      next: page => {
        const known = new Set(this.view.results().map(r => r.id));
        this.view.results.update(list => [...list, ...page.recipes.filter(r => !known.has(r.id))]);
        this.applyPage(page);
        this.loadingMore.set(false);
      },
      error: () => {
        this.error.set('No pudimos cargar más recetas. Inténtalo de nuevo.');
        this.loadingMore.set(false);
      },
    });
  }

  private applyPage(page: { nextOffset: number; hasMore: boolean; total: number; ingredientsTotal: number | null; bestMatchCount: number | null }): void {
    this.view.nextOffset.set(page.nextOffset);
    this.hasMore.set(page.hasMore);
    this.total.set(page.total);
    this.ingredientsTotal.set(page.ingredientsTotal ?? 0);
    this.bestMatchCount.set(page.bestMatchCount ?? 0);
  }

  /** El asistente recibe las recetas que se están mostrando. */
  private shareWithChat(): void {
    const chat = inject(ChatService);
    effect(() => chat.setVisibleRecipes(this.visibleResults()));
    inject(DestroyRef).onDestroy(() => chat.setVisibleRecipes([]));
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }

  onHide(id: string): void {
    this.recipeService.hide(id);
  }
}
