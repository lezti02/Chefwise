import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { RecipeApiService } from './recipe-api.service';
import { itemDto, recipeDto, recommendationsResponse } from '../testing/api-fixtures';

describe('RecipeApiService', () => {
  let api: RecipeApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(RecipeApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('POST /recommendations envía las preferencias y convierte la respuesta en recetas', () => {
    let result: ReturnType<typeof Object> | undefined;
    const request = {
      tags: ['Comida rápida'],
      difficulty: 'facil' as const,
      max_time: 30,
      countries: [],
      exclude_ids: [],
      top_n: 5,
    };

    api.recommend(request).subscribe(r => (result = r));

    const req = http.expectOne(r => r.url.endsWith('/recommendations'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(request);
    req.flush(recommendationsResponse([itemDto(123, { name: 'Tacos reales', total_time_min: null, country: null })]));

    const [recipe] = result as any[];
    expect(recipe.id).toBe('123');
    expect(recipe.name).toBe('Tacos reales');
    expect(recipe.minutes).toBeNull();
    expect(recipe.country).toBeNull();
    expect(recipe.ingredients).toEqual([
      { name: '2 huevos', amount: '' },
      { name: '1 taza de leche', amount: '' },
    ]);
    expect(recipe.steps).toEqual([]);
  });

  it('GET /recipes/{id} trae ingredientes y pasos tal cual los devuelve el backend', () => {
    let result: any;
    api.getRecipe('42').subscribe(r => (result = r));

    const req = http.expectOne(r => r.url.endsWith('/recipes/42'));
    expect(req.request.method).toBe('GET');
    req.flush(recipeDto(42, { instructions: ['Paso uno real', 'Paso dos real'] }));

    expect(result.id).toBe('42');
    expect(result.steps).toEqual(['Paso uno real', 'Paso dos real']);
  });

  it('POST /recommendations/by-ingredients', () => {
    api.recommendByIngredients({ ingredients: ['pollo'], exclude_ids: [], top_n: 5 }).subscribe();
    const req = http.expectOne(r => r.url.endsWith('/recommendations/by-ingredients'));
    expect(req.request.body.ingredients).toEqual(['pollo']);
    req.flush(recommendationsResponse([]));
  });

  it('GET /metadata devuelve tags y países exactos', () => {
    let result: any;
    api.getMetadata().subscribe(value => (result = value));
    http.expectOne(r => r.url.endsWith('/metadata')).flush({ tags: ['Cena'], countries: ['México'] });
    expect(result).toEqual({ tags: ['Cena'], countries: ['México'] });
  });

  it('GET /recipes/search envía query, tag, límite y offset, y devuelve el total de coincidencias', () => {
    let page: any;
    api.searchRecipes('tacos', 'Cena', 5, 10).subscribe(p => (page = p));
    const req = http.expectOne(r => r.url.endsWith('/recipes/search'));
    expect(req.request.params.get('q')).toBe('tacos');
    expect(req.request.params.get('tag')).toBe('Cena');
    expect(req.request.params.get('top_n')).toBe('5');
    expect(req.request.params.get('offset')).toBe('10');
    req.flush(recommendationsResponse([itemDto(1)], { candidates: 77, has_more: true }));
    expect(page.total).toBe(77);
    expect(page.hasMore).toBe(true);
    expect(page.recipes.length).toBe(1);
  });

  it('by-ingredients conserva qué ingredientes usa cada receta y cuántos extras lleva', () => {
    let page: any;
    api
      .recommendByIngredients({ ingredients: ['pollo', 'arroz'], exclude_ids: [], top_n: 5, offset: 5, fewest_extras: true })
      .subscribe(p => (page = p));
    const req = http.expectOne(r => r.url.endsWith('/recommendations/by-ingredients'));
    expect(req.request.body).toMatchObject({ offset: 5, fewest_extras: true });
    req.flush(
      recommendationsResponse([itemDto(3, { matched_ingredients: ['pollo'], extra_ingredients: 4 })], {
        ingredients_total: 2,
        best_match_count: 1,
        has_more: true,
      })
    );
    expect(page.recipes[0].matchedIngredients).toEqual(['pollo']);
    expect(page.recipes[0].extraIngredients).toBe(4);
    expect(page.ingredientsTotal).toBe(2);
    expect(page.bestMatchCount).toBe(1);
  });
});
