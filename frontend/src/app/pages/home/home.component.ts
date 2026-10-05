import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { RecipeRowComponent } from '../../shared/recipe-row/recipe-row.component';
import { ChatService } from '../../services/chat.service';
import { RecipeService } from '../../services/recipe.service';
import { ViewStateService } from '../../services/view-state.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, RecipeRowComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  // Estado que se conserva al salir y volver (ver ViewStateService).
  private view = inject(ViewStateService).home;
  searchTerm = this.view.searchTerm;
  committedQuery = this.view.committedQuery;
  searchActive = this.view.active;
  total = this.view.total;
  hasMore = this.view.hasMore;

  loading = signal(false);
  loadingMore = signal(false);
  searchError = signal<string | null>(null);

  recent = computed(() => this.recipeService.history().slice(0, 5));
  /** Lo recibido del backend, sin las recetas ocultas ni las que llevan alérgenos del usuario. */
  searchResults = computed(() =>
    this.recipeService.filterForUser(this.view.results()).map(r => this.recipeService.decorate(r))
  );
  private request?: Subscription;
  chatService = inject(ChatService);

  constructor(public recipeService: RecipeService) {
    inject(DestroyRef).onDestroy(() => this.request?.unsubscribe());
    // El asistente recibe las recetas que se están mostrando.
    effect(() => this.chatService.setVisibleRecipes(this.searchActive() ? this.searchResults() : this.recent()));
    inject(DestroyRef).onDestroy(() => this.chatService.setVisibleRecipes([]));
  }

  openAssistant(): void {
    this.chatService.openChat();
  }

  /** Nueva búsqueda: empieza desde la primera página. */
  search(): void {
    const query = this.searchTerm().trim();
    if (!query) return;
    this.request?.unsubscribe();
    this.searchActive.set(true);
    this.committedQuery.set(query);
    this.view.results.set([]);
    this.total.set(0);
    this.hasMore.set(false);
    this.loading.set(true);
    this.loadingMore.set(false);
    this.searchError.set(null);
    this.request = this.recipeService.searchCatalog(query, null, 0).subscribe({
      next: page => {
        this.view.results.set(page.recipes);
        this.total.set(page.total);
        this.hasMore.set(page.hasMore);
        this.loading.set(false);
      },
      error: () => {
        this.searchError.set('No pudimos buscar en el catálogo. Inténtalo de nuevo.');
        this.loading.set(false);
      },
    });
  }

  /** Trae las siguientes recetas de la misma búsqueda y las agrega al final. */
  loadMore(): void {
    if (this.loading() || this.loadingMore() || !this.hasMore()) return;
    this.request?.unsubscribe();
    this.loadingMore.set(true);
    this.searchError.set(null);
    const offset = this.view.results().length;
    this.request = this.recipeService.searchCatalog(this.committedQuery(), null, offset).subscribe({
      next: page => {
        const known = new Set(this.view.results().map(r => r.id));
        this.view.results.update(list => [...list, ...page.recipes.filter(r => !known.has(r.id))]);
        this.total.set(page.total);
        this.hasMore.set(page.hasMore);
        this.loadingMore.set(false);
      },
      error: () => {
        this.searchError.set('No pudimos cargar más recetas. Inténtalo de nuevo.');
        this.loadingMore.set(false);
      },
    });
  }

  clearSearch(): void {
    this.request?.unsubscribe();
    this.searchTerm.set('');
    this.committedQuery.set('');
    this.view.results.set([]);
    this.total.set(0);
    this.hasMore.set(false);
    this.searchError.set(null);
    this.loading.set(false);
    this.loadingMore.set(false);
    this.searchActive.set(false);
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }
}
