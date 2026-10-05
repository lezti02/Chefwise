/**
 * Contrato HTTP con el backend (espejo de backend/schemas.py).
 * Los nombres de campo son los del dataset (snake_case).
 */

import { Difficulty, MealCategory } from './recipe.model';

export interface RecommendationRequestDto {
  tags: string[];
  difficulty: Difficulty | null;
  max_time: number | null;
  countries: string[];
  exclude_ids: number[];
  top_n: number;
}

export interface IngredientsRequestDto {
  ingredients: string[];
  exclude_ids: number[];
  top_n: number;
  /** Cuántos resultados saltar (para "buscar más opciones"). */
  offset?: number;
  /** true = primero lo que aprovecha más ingredientes con menos extras. */
  fewest_extras?: boolean;
}

export interface RecipeSummaryDto {
  recipe_id: number;
  name: string;
  ingredients: string[];
  difficulty: Difficulty | null;
  total_time_min: number | null;
  servings: number | null;
  country: string | null;
  category: MealCategory | null;
  meal_type: string | null;
  source: string | null;
  source_url: string | null;
}

export interface RecommendationItemDto extends RecipeSummaryDto {
  similarity: number | null;
  score: number;
  /** Solo en "Con lo que tengo": ingredientes del usuario que la receta usa. */
  matched_ingredients?: string[] | null;
  /** Solo en "Con lo que tengo": ingredientes de la receta que el usuario no tiene. */
  extra_ingredients?: number | null;
}

export interface RecommendationResponseDto {
  recommendations: RecommendationItemDto[];
  meta: {
    candidates: number;
    query_text: string | null;
    applied_max_time: number | null;
    relaxed: string[];
    has_more?: boolean;
    ingredients_total?: number | null;
    best_match_count?: number | null;
  };
}

export interface MetadataDto {
  tags: string[];
  countries: string[];
}

export interface RecipeDto extends RecipeSummaryDto {
  instructions: string[];
  difficulty_source: string | null;
  prep_time_min: number | null;
  cook_time_min: number | null;
  category_tags: string[];
  diet_tags: string[];
  description: string | null;
  num_comments: number | null;
}

export interface ChatRequestDto {
  message: string;
  history: { role: 'user' | 'bot'; text: string }[];
  recipe_id: number | null;
  visible_recipe_ids: number[];
  /** Alergias/restricciones activas del usuario (etiquetas de "Mi cocina"). */
  allergies: string[];
  /** Paso en el que va el usuario; null mientras la UI no lo registre. */
  current_step: number | null;
}

export interface ChatResponseDto {
  reply: string;
}
