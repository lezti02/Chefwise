import { Location } from '@angular/common';
import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { Observable, catchError, map, of, startWith, switchMap } from 'rxjs';
import { RecipeService } from '../../services/recipe.service';
import { ChatService } from '../../services/chat.service';
import { DIFFICULTY_LABELS, Recipe } from '../../models/recipe.model';

type DetailState =
  | { status: 'loading' }
  | { status: 'ok'; recipe: Recipe }
  | { status: 'not-found' }
  | { status: 'error' };

@Component({
  selector: 'app-recipe-detail',
  standalone: true,
  templateUrl: './recipe-detail.component.html',
  styleUrl: './recipe-detail.component.scss',
})
export class RecipeDetailComponent {
  private route = inject(ActivatedRoute);
  private recipeService = inject(RecipeService);
  private location = inject(Location);
  cookedAnnouncement = signal('');

  difficultyLabels = DIFFICULTY_LABELS;

  /** GET /recipes/{id} cada vez que cambia el :id de la URL. */
  state = toSignal(
    this.route.paramMap.pipe(
      map(p => p.get('id') ?? ''),
      switchMap(id => this.load(id))
    ),
    { initialValue: { status: 'loading' } as DetailState }
  );

  recipe = computed(() => {
    const s = this.state();
    return s.status === 'ok' ? this.recipeService.decorate(s.recipe) : null;
  });

  /** La receta abierta está en la lista de "no volver a mostrar". */
  isHidden = computed(() => {
    const r = this.recipe();
    return !!r && this.recipeService.isHidden(r.id);
  });

  allergens = computed(() => {
    const r = this.recipe();
    return r ? this.recipeService.allergensIn(r) : [];
  });

  constructor() {
    // El asistente responde sobre la receta abierta.
    const chat = inject(ChatService);
    effect(() => chat.setFocusRecipe(this.recipe()));
    inject(DestroyRef).onDestroy(() => chat.setFocusRecipe(null));
  }

  private load(id: string): Observable<DetailState> {
    if (!/^\d+$/.test(id)) return of({ status: 'not-found' });
    return this.recipeService.loadRecipe(id).pipe(
      map((recipe): DetailState => ({ status: 'ok', recipe })),
      catchError((e: unknown) =>
        of<DetailState>({ status: e instanceof HttpErrorResponse && (e.status === 404 || e.status === 422) ? 'not-found' : 'error' })
      ),
      startWith<DetailState>({ status: 'loading' })
    );
  }

  toggleFavorite(): void {
    const r = this.recipe();
    if (r) this.recipeService.toggleFavorite(r.id);
  }

  toggleSaved(): void {
    const r = this.recipe();
    if (r) this.recipeService.toggleSaved(r.id);
  }

  /** "No volver a mostrar": la receta deja de salir en recomendaciones (se puede deshacer). */
  hide(): void {
    const r = this.recipe();
    if (r) {
      this.recipeService.hide(r.id);
      this.cookedAnnouncement.set(`No volveremos a mostrarte ${r.name}.`);
    }
  }

  unhide(): void {
    const r = this.recipe();
    if (r) {
      this.recipeService.unhide(r.id);
      this.cookedAnnouncement.set(`${r.name} volverá a aparecer en tus recomendaciones.`);
    }
  }

  /**
   * "Cociné esto": registra la receta en el historial (RecipeService.markCooked).
   * Esto es justo lo que alimenta la pestaña "Historial" y "Resumen" de Mi cocina.
   */
  markCooked(): void {
    const r = this.recipe();
    if (r) {
      this.recipeService.markCooked(r.id);
      this.cookedAnnouncement.set(`${r.name} se agregó a tu historial.`);
    }
  }

  removeFromHistory(): void {
    const r = this.recipe();
    if (r) {
      this.recipeService.removeFromHistory(r.id);
      this.cookedAnnouncement.set(`${r.name} se quitó de tu historial.`);
    }
  }

  goBack(): void {
    this.location.back();
  }
}
