import { Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { ChatService } from '../../services/chat.service';
import { RecipeService, SurpriseQuery } from '../../services/recipe.service';
import { ViewStateService } from '../../services/view-state.service';
import { Difficulty } from '../../models/recipe.model';

export interface CategoryGroup {
  title: string;
  tags: string[];
}

const CATEGORY_GROUPS: { title: string; tags: string[] }[] = [
  {
    title: 'Tiempos de comida',
    tags: ['Desayuno', 'Comida', 'Cena'],
  },
  {
    title: 'Tipo de plato',
    tags: ['Sopa', 'Pasta', 'Postre', 'Bebida', 'Alcohol'],
  },
  {
    title: 'Proteínas y carnes',
    tags: ['Pollo', 'Res', 'Cerdo', 'Mariscos', 'Pavo', 'Cordero'],
  },
  {
    title: 'Estilo de alimentación',
    tags: ['Vegetariana', 'Vegana'],
  },
];

@Component({
  selector: 'app-surprise',
  standalone: true,
  imports: [RouterLink, RecipeCardComponent],
  templateUrl: './surprise.component.html',
  styleUrl: './surprise.component.scss',
})
export class SurpriseComponent {
  // Filtros y recetas mostradas: se conservan al salir y volver (ver ViewStateService).
  private view = inject(ViewStateService).surprise;

  tags = signal<string[]>([]);
  countries = signal<string[]>([]);
  selectedTags = this.view.selectedTags;
  selectedCountry = this.view.country;
  metadataLoading = signal(true);
  metadataError = signal(false);

  categoryGroups = computed<CategoryGroup[]>(() => {
    const allTags = this.tags();
    if (!allTags.length) return [];
    const availableSet = new Set(allTags);
    const assigned = new Set<string>();

    const groups: CategoryGroup[] = [];
    for (const group of CATEGORY_GROUPS) {
      const matched = group.tags.filter(t => availableSet.has(t));
      if (matched.length > 0) {
        groups.push({ title: group.title, tags: matched });
        matched.forEach(t => assigned.add(t));
      }
    }

    const unassigned = allTags.filter(t => !assigned.has(t));
    if (unassigned.length > 0) {
      groups.push({ title: 'Otras categorías', tags: unassigned });
    }
    return groups;
  });

  difficulties: { value: Difficulty; label: string }[] = [
    { value: 'facil', label: 'Sencillo' },
    { value: 'intermedio', label: 'Intermedio' },
    { value: 'reto', label: 'Me reto hoy' },
  ];
  selectedDifficulty = this.view.difficulty;

  readonly minMinutes = 5;
  readonly maxMinutesLimit = 120;
  readonly minutesStep = 5;
  maxMinutes = this.view.maxMinutes;
  anyTime = this.view.anyTime;

  loading = signal(false);
  error = signal<string | null>(null);

  private suggestions = this.view.suggestions;
  /** Se recalcula solo si el usuario oculta una receta, cambia sus alergias o marca favoritas. */
  visibleSuggestions = computed(() =>
    this.recipeService.filterForUser(this.suggestions()).map(r => this.recipeService.decorate(r))
  );

  private destroyRef = inject(DestroyRef);
  private request?: Subscription;
  /** Para que aplicar los mismos filtros no repita las recetas ya mostradas. */
  private shown = this.view.shown;

  constructor(public recipeService: RecipeService) {
    this.destroyRef.onDestroy(() => {
      this.request?.unsubscribe();
      this.metadataRequest?.unsubscribe();
    });
    this.metadataRequest = this.recipeService.getMetadata().subscribe({
      next: metadata => {
        this.tags.set(metadata.tags);
        this.countries.set(metadata.countries);
        this.metadataLoading.set(false);
      },
      error: () => {
        this.metadataError.set(true);
        this.metadataLoading.set(false);
      },
    });
    this.shareWithChat();
  }

  private metadataRequest?: Subscription;

  toggleTag(tag: string): void {
    this.selectedTags.update(list => (list.includes(tag) ? list.filter(x => x !== tag) : [...list, tag]));
  }

  setDifficulty(d: Difficulty): void {
    this.selectedDifficulty.set(d);
  }

  setCountry(value: string): void {
    this.selectedCountry.set(value || null);
  }

  setMinutes(value: string | number): void {
    const minutes = Math.round(Number(value) / this.minutesStep) * this.minutesStep;
    if (Number.isFinite(minutes)) {
      this.maxMinutes.set(Math.min(this.maxMinutesLimit, Math.max(this.minMinutes, minutes)));
    }
  }

  /** Permitir/ocultar recetas con tus alergias; si ya hay ideas, se piden de nuevo con el nuevo criterio. */
  setAllowAllergens(value: boolean): void {
    this.recipeService.setAllowAllergenRecipes(value);
    if (this.suggestions().length || this.shown.ids.size) {
      this.shown.ids.clear();
      this.showIdeas();
    }
  }

  setAnyTime(value: boolean): void {
    this.anyTime.set(value);
  }

  /** Estado actual de los controles, listo para el backend (POST /recommendations). */
  private currentQuery(): SurpriseQuery {
    return {
      tags: this.selectedTags(),
      difficulty: this.selectedDifficulty(),
      maxMinutes: this.anyTime() ? null : this.maxMinutes(),
      country: this.selectedCountry(),
    };
  }

  /**
   * Pide ideas al recomendador real. Con los mismos controles que la vez
   * anterior se excluyen las recetas ya mostradas, para que "Mostrar ideas
   * nuevas" realmente traiga ideas nuevas; si cambian los controles, se empieza de cero.
   */
  showIdeas(): void {
    const query = this.currentQuery();
    const key = JSON.stringify(query);
    if (key !== this.shown.queryKey) this.shown.ids.clear();
    this.shown.queryKey = key;
    this.fetch(query, [...this.shown.ids], true);
  }

  private fetch(query: SurpriseQuery, exclude: string[], allowRetry: boolean): void {
    this.request?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);

    this.request = this.recipeService.getSurpriseSuggestions({ ...query, extraExcludeIds: exclude }).subscribe({
      next: list => {
        if (!list.length && exclude.length && allowRetry) {
          // Ya se mostró todo lo que cumple: vuelve a empezar con los mismos filtros.
          this.shown.ids.clear();
          this.fetch(query, [], false);
          return;
        }
        list.forEach(r => this.shown.ids.add(r.id));
        this.suggestions.set(list);
        this.loading.set(false);
      },
      error: () => {
        this.suggestions.set([]);
        this.error.set('No pudimos obtener ideas del servidor. Revisa que el backend esté en marcha e inténtalo de nuevo.');
        this.loading.set(false);
      },
    });
  }

  /** El asistente recibe las recetas que se están mostrando. */
  private shareWithChat(): void {
    const chat = inject(ChatService);
    effect(() => chat.setVisibleRecipes(this.visibleSuggestions()));
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
