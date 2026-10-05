import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { environment } from '../../environments/environment';
import { ChatRequestDto, ChatResponseDto } from '../models/api.model';
import { RecipeService } from './recipe.service';

export interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
}

/** Lo mínimo de una receta para dar contexto al asistente. */
export interface ChatRecipeRef {
  id: string;
  name: string;
}

/** Máximo de recetas de una lista que se mandan como contexto (igual que el backend). */
const MAX_VISIBLE = 12;
/** Turnos previos que se reenvían al backend (el modelo no guarda estado). */
const MAX_HISTORY = 20;

/**
 * ChefWise, el asistente de cocina. POST /chat con la pregunta, el historial y las recetas
 * que el usuario está viendo: la abierta en el detalle (`focusRecipe`) y las
 * de la lista actual (`visibleRecipes`). Las páginas actualizan ese contexto.
 */
@Injectable({ providedIn: 'root' })
export class ChatService {
  private http = inject(HttpClient);
  private recipeService = inject(RecipeService);
  private baseUrl = environment.apiUrl.replace(/\/+$/, '');

  private readonly _messages = signal<ChatMessage[]>([
    { role: 'bot', text: 'Puedes preguntarme en cualquier momento: sustituciones, tiempos de cocción, conversión de unidades, o si algo ya está listo.' },
  ]);
  readonly messages = this._messages.asReadonly();

  private readonly _pending = signal(false);
  readonly pending = this._pending.asReadonly();

  private readonly _isOpen = signal(false);
  readonly isOpen = this._isOpen.asReadonly();

  openChat(): void {
    this._isOpen.set(true);
  }

  closeChat(): void {
    this._isOpen.set(false);
  }

  toggleChat(): void {
    this._isOpen.update(v => !v);
  }

  private readonly focusRecipe = signal<ChatRecipeRef | null>(null);
  private readonly visibleRecipes = signal<ChatRecipeRef[]>([]);

  /** Texto para la cabecera del chat: de qué receta(s) se está hablando. */
  readonly contextLabel = computed(() => {
    const focus = this.focusRecipe();
    if (focus) return focus.name;
    const n = Math.min(this.visibleRecipes().length, MAX_VISIBLE);
    return n ? `${n} receta${n === 1 ? '' : 's'} en pantalla` : null;
  });

  setFocusRecipe(recipe: ChatRecipeRef | null): void {
    this.focusRecipe.set(recipe ? { id: recipe.id, name: recipe.name } : null);
  }

  setVisibleRecipes(recipes: ChatRecipeRef[]): void {
    this.visibleRecipes.set(recipes.slice(0, MAX_VISIBLE).map(r => ({ id: r.id, name: r.name })));
  }

  ask(text: string): void {
    const message = text.trim();
    if (!message || this._pending()) return;

    const history = this._messages().slice(-MAX_HISTORY);
    this._messages.update(list => [...list, { role: 'user', text: message }]);
    this._pending.set(true);

    const focus = this.focusRecipe();
    const body: ChatRequestDto = {
      message,
      history,
      recipe_id: focus ? Number(focus.id) : null,
      visible_recipe_ids: this.visibleRecipes().map(r => Number(r.id)),
      // Solo las alergias: ChefWise las usa para advertir y filtrar sustituciones.
      allergies: this.recipeService.activeAllergyLabels(),
      current_step: null,
    };

    this.http.post<ChatResponseDto>(`${this.baseUrl}/chat`, body).subscribe({
      next: res => this.reply(res.reply),
      error: (e: unknown) => this.reply(errorText(e)),
    });
  }

  private reply(text: string): void {
    this._messages.update(list => [...list, { role: 'bot', text }]);
    this._pending.set(false);
  }
}

function errorText(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    if (e.status === 503 && typeof e.error?.detail === 'string') return e.error.detail;
    if (e.status === 0) return 'No pude conectar con el servidor. Revisa que el backend esté en marcha.';
  }
  return 'Ocurrió un error al consultar al asistente. Inténtalo de nuevo.';
}
