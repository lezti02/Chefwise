import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { RecipeDetailComponent } from './recipe-detail.component';
import { recipeDto } from '../../testing/api-fixtures';
import { RecipeService } from '../../services/recipe.service';

describe('RecipeDetailComponent (GET /recipes/{id})', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([{ path: 'receta/:id', component: RecipeDetailComponent }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });

  afterEach(() => http.verify());

  it('abre la receta con el recipe_id de la URL y muestra ingredientes y pasos del backend', async () => {
    await harness.navigateByUrl('/receta/123', RecipeDetailComponent);

    const req = http.expectOne(r => r.url.endsWith('/recipes/123'));
    req.flush(
      recipeDto(123, {
        name: 'Tacos de pollo reales',
        ingredients: ['500 g de pechuga', '12 tortillas'],
        instructions: ['Cuece el pollo.', 'Calienta las tortillas.'],
        total_time_min: null,
      })
    );
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('Tacos de pollo reales');
    expect(Array.from(el.querySelectorAll('.ing-list li')).map(li => li.querySelector('span')?.textContent)).toEqual([
      '500 g de pechuga',
      '12 tortillas',
    ]);
    expect(Array.from(el.querySelectorAll('.steps li')).map(li => li.textContent?.trim())).toEqual([
      'Cuece el pollo.',
      'Calienta las tortillas.',
    ]);
    // Tiempo desconocido en el dataset => no se inventa un "0 min".
    expect(el.querySelector('.detail-meta')?.textContent).not.toContain('min');
  });

  it('abrir una receta la registra como vista para el recomendador', async () => {
    await harness.navigateByUrl('/receta/123', RecipeDetailComponent);
    http.expectOne(r => r.url.endsWith('/recipes/123')).flush(recipeDto(123, { name: 'Tacos de pollo reales' }));
    await harness.fixture.whenStable();
    harness.detectChanges();

    const service = TestBed.inject(RecipeService);
    expect(service.recentViewIds()).toEqual(['123']);
    expect(service.hasTasteProfile()).toBe(true);
  });

  it('si la receta no trae instrucciones no inventa pasos', async () => {
    await harness.navigateByUrl('/receta/5', RecipeDetailComponent);
    http.expectOne(r => r.url.endsWith('/recipes/5')).flush(recipeDto(5, { instructions: [] }));
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    expect(el.querySelectorAll('.steps li').length).toBe(0);
    expect(el.textContent).toContain('no tiene instrucciones registradas');
  });

  it('Cociné esto cambia el estado visible y permite quitar del historial', async () => {
    await harness.navigateByUrl('/receta/7', RecipeDetailComponent);
    http.expectOne(r => r.url.endsWith('/recipes/7')).flush(recipeDto(7, { name: 'Sopa' }));
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    el.querySelector<HTMLButtonElement>('button[title="Favorita"]')!.click();
    el.querySelector<HTMLButtonElement>('button[title="Guardar para después"]')!.click();
    const cookedButton = Array.from(el.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === 'Cociné esto')!;
    cookedButton.click();
    harness.detectChanges();
    expect(el.textContent).toContain('Cocinado ✓');
    expect(el.querySelector('[aria-live="polite"]')?.textContent).toContain('se agregó');

    const removeButton = Array.from(el.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.includes('Quitar del historial'))!;
    removeButton.click();
    harness.detectChanges();
    expect(el.textContent).toContain('Cociné esto');
    expect(el.querySelector('button[title="Favorita"]')?.classList).toContain('on');
    expect(el.querySelector('button[title="Guardar para después"]')?.classList).toContain('on');
  });

  it('receta inexistente (404) muestra "No encontramos esta receta."', async () => {
    await harness.navigateByUrl('/receta/99999999', RecipeDetailComponent);
    http
      .expectOne(r => r.url.endsWith('/recipes/99999999'))
      .flush({ detail: 'No existe' }, { status: 404, statusText: 'Not Found' });
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect((harness.routeNativeElement as HTMLElement).textContent).toContain('No encontramos esta receta.');
  });

  it('"No volver a mostrar" oculta la receta, avisa y se puede deshacer', async () => {
    await harness.navigateByUrl('/receta/9', RecipeDetailComponent);
    http.expectOne(r => r.url.endsWith('/recipes/9')).flush(recipeDto(9, { name: 'Pozole' }));
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    const service = TestBed.inject(RecipeService);
    const button = (text: string) =>
      Array.from(el.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text);

    expect(service.isHidden('9')).toBe(false);
    button('No volver a mostrar')!.click();
    harness.detectChanges();

    expect(service.isHidden('9')).toBe(true);
    expect(service.lastHidden()?.name).toBe('Pozole'); // alimenta el aviso "Deshacer"
    expect(button('No volver a mostrar')).toBeUndefined();

    button('Mostrar de nuevo')!.click();
    harness.detectChanges();
    expect(service.isHidden('9')).toBe(false);
    expect(button('No volver a mostrar')).toBeDefined();
  });
});
