import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  IngredientsRequestDto,
  MetadataDto,
  RecipeDto,
  RecipeSummaryDto,
  RecommendationItemDto,
  RecommendationRequestDto,
  RecommendationResponseDto,
} from '../models/api.model';
import { Recipe, RecipePage } from '../models/recipe.model';

/** Cliente HTTP del backend. Solo habla con la API y convierte DTO → Recipe. */
@Injectable({ providedIn: 'root' })
export class RecipeApiService {
  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl.replace(/\/+$/, '');

  /** POST /recommendations */
  recommend(request: RecommendationRequestDto): Observable<Recipe[]> {
    return this.http
      .post<RecommendationResponseDto>(`${this.baseUrl}/recommendations`, request)
      .pipe(map(res => res.recommendations.map(toRecipe)));
  }

  /** POST /recommendations/by-ingredients */
  recommendByIngredients(request: IngredientsRequestDto): Observable<RecipePage> {
    return this.http
      .post<RecommendationResponseDto>(`${this.baseUrl}/recommendations/by-ingredients`, request)
      .pipe(map(toPage));
  }

  /** GET /metadata — valores exactos disponibles en el CSV. */
  getMetadata(): Observable<MetadataDto> {
    return this.http.get<MetadataDto>(`${this.baseUrl}/metadata`);
  }

  /** GET /recipes/search — búsqueda sobre el catálogo completo. */
  searchRecipes(query: string, tag: string | null = null, topN = 5, offset = 0): Observable<RecipePage> {
    let params = new HttpParams().set('q', query).set('top_n', topN);
    if (offset) params = params.set('offset', offset);
    if (tag) params = params.set('tag', tag);
    return this.http
      .get<RecommendationResponseDto>(`${this.baseUrl}/recipes/search`, { params })
      .pipe(map(toPage));
  }

  /** GET /recipes/{recipe_id} — receta completa con pasos. */
  getRecipe(id: string): Observable<Recipe> {
    return this.http.get<RecipeDto>(`${this.baseUrl}/recipes/${encodeURIComponent(id)}`).pipe(map(toRecipe));
  }
}

/** Respuesta de recomendación → página de recetas con sus totales. */
function toPage(res: RecommendationResponseDto): RecipePage {
  return {
    recipes: res.recommendations.map(toRecipe),
    total: res.meta.candidates,
    hasMore: res.meta.has_more ?? false,
    ingredientsTotal: res.meta.ingredients_total ?? null,
    bestMatchCount: res.meta.best_match_count ?? null,
  };
}

/** Convierte lo que devuelve el backend en el modelo de UI (sin inventar campos). */
export function toRecipe(dto: RecipeSummaryDto | RecipeDto): Recipe {
  return {
    id: String(dto.recipe_id),
    name: dto.name,
    category: dto.category,
    country: dto.country,
    minutes: dto.total_time_min,
    servings: dto.servings,
    difficulty: dto.difficulty,
    sourceUrl: dto.source_url,
    neverCooked: true,
    isFavorite: false,
    isSaved: false,
    lastCookedAt: null,
    ingredients: dto.ingredients.map(line => ({ name: line, amount: '' })),
    steps: 'instructions' in dto ? dto.instructions : [],
    // Solo los resultados de "Con lo que tengo" traen estos dos campos.
    matchedIngredients: (dto as Partial<RecommendationItemDto>).matched_ingredients,
    extraIngredients: (dto as Partial<RecommendationItemDto>).extra_ingredients,
  };
}
