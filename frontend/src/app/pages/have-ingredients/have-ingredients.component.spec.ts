import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { itemDto, recommendationsResponse } from '../../testing/api-fixtures';
import { HaveIngredientsComponent } from './have-ingredients.component';

describe('HaveIngredientsComponent (Con lo que tengo)', () => {
  let http: HttpTestingController;
  type Fixture = ReturnType<typeof TestBed.createComponent<HaveIngredientsComponent>>;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const request = () => http.expectOne(r => r.url.endsWith('/recommendations/by-ingredients'));
  const used = (id: number, matched: string[], extra: number) =>
    itemDto(id, { name: `Receta ${id}`, matched_ingredients: matched, extra_ingredients: extra });
  const button = (el: HTMLElement, text: string) =>
    Array.from(el.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === text)!;

  async function settle(fixture: Fixture) {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  function addIngredients(fixture: Fixture, names: string[]) {
    const input = (fixture.nativeElement as HTMLElement).querySelector<HTMLInputElement>('.tag-input input')!;
    for (const name of names) {
      input.value = name;
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    }
    fixture.detectChanges();
  }

  it('ya no ofrece "Solo con esto" ni "1–2 extras": hay un interruptor de menor número de extras', () => {
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).not.toContain('Solo con esto');
    expect(el.textContent).not.toContain('Permitir 1–2 extras');
    expect(el.textContent).toContain('Con el menor número de ingredientes extra');
    expect(el.querySelector<HTMLInputElement>('#fewest-extras')!.type).toBe('checkbox');
  });

  it('manda las recetas cocinadas para personalizar el orden', async () => {
    localStorage.setItem(
      'chefwise.recipeState',
      JSON.stringify({ '15': { isFavorite: false, isSaved: false, lastCookedAt: '2026-01-01T00:00:00.000Z' } })
    );
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('ya has marcado o cocinado');
    addIngredients(fixture, ['pollo']);
    button(el, 'Buscar qué puedo cocinar').click();
    const req = request();
    expect(req.request.body.cooked_ids).toEqual([15]);
    req.flush(recommendationsResponse([used(1, ['pollo'], 2)]));
    await settle(fixture);
  });

  it('manda fewest_extras según el interruptor', async () => {
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    addIngredients(fixture, ['pollo']);

    const toggle = el.querySelector<HTMLInputElement>('#fewest-extras')!;
    expect(toggle.checked).toBe(true);
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    button(el, 'Buscar qué puedo cocinar').click();

    const req = request();
    expect(req.request.body).toMatchObject({ ingredients: ['pollo'], fewest_extras: false, offset: 0, top_n: 5 });
    req.flush(recommendationsResponse([used(1, ['pollo'], 3)]));
    await settle(fixture);
  });

  it('indica cuántos ingredientes usa cada receta y cuántos extras lleva', async () => {
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    addIngredients(fixture, ['pollo', 'arroz']);
    button(el, 'Buscar qué puedo cocinar').click();
    request().flush(
      recommendationsResponse([used(1, ['pollo', 'arroz'], 0), used(2, ['pollo'], 1)], {
        ingredients_total: 2,
        best_match_count: 2,
        has_more: false,
      })
    );
    await settle(fixture);

    const cards = Array.from(el.querySelectorAll('a.rcard'));
    expect(cards[0].querySelector('.usage')?.textContent).toContain('Usa 2 de tus 2 ingredientes: pollo, arroz');
    expect(cards[0].querySelector('.usage-extra')?.textContent).toContain('Sin ingredientes extra');
    expect(cards[1].querySelector('.usage')?.textContent).toContain('Usa 1 de tus 2 ingredientes: pollo');
    expect(cards[1].querySelector('.usage-extra')?.textContent).toContain('1 ingrediente extra');
    expect(el.querySelector('.coverage-note')).toBeNull(); // sí existen recetas que usan todo
  });

  it('si ninguna receta usa todos los ingredientes lo dice y cuántos sí se usarán', async () => {
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    addIngredients(fixture, ['pollo', 'arroz', 'chocolate']);
    button(el, 'Buscar qué puedo cocinar').click();
    request().flush(
      recommendationsResponse([used(1, ['pollo', 'arroz'], 2)], { ingredients_total: 3, best_match_count: 2, has_more: false })
    );
    await settle(fixture);

    const note = el.querySelector('.coverage-note')?.textContent ?? '';
    expect(note).toContain('Ninguna receta usa los 3 ingredientes');
    expect(note).toContain('2 de 3');
  });

  it('"Buscar más opciones" agrega la siguiente tanda con la misma búsqueda', async () => {
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    addIngredients(fixture, ['pollo']);
    button(el, 'Buscar qué puedo cocinar').click();
    request().flush(
      recommendationsResponse([1, 2, 3, 4, 5].map(id => used(id, ['pollo'], id)), { ingredients_total: 1, best_match_count: 1, has_more: true })
    );
    await settle(fixture);
    expect(el.querySelectorAll('a.rcard').length).toBe(5);

    // Cambiar lo escrito después de buscar no altera la búsqueda que se está paginando.
    addIngredients(fixture, ['arroz']);
    button(el, 'Buscar más opciones').click();
    const req = request();
    expect(req.request.body).toMatchObject({ ingredients: ['pollo'], offset: 5, top_n: 5 });
    req.flush(recommendationsResponse([6, 7].map(id => used(id, ['pollo'], id)), { ingredients_total: 1, best_match_count: 1, has_more: false }));
    await settle(fixture);

    expect(el.querySelectorAll('a.rcard').length).toBe(7);
    expect(el.textContent).not.toContain('Buscar más opciones');
    expect(el.textContent).toContain('Ya no hay más recetas');
  });

  it('al volver conserva ingredientes, opciones y recetas mostradas', async () => {
    const first = TestBed.createComponent(HaveIngredientsComponent);
    first.detectChanges();
    const firstEl = first.nativeElement as HTMLElement;
    addIngredients(first, ['pollo', 'arroz']);
    const toggle = firstEl.querySelector<HTMLInputElement>('#fewest-extras')!;
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change'));
    button(firstEl, 'Buscar qué puedo cocinar').click();
    request().flush(
      recommendationsResponse([1, 2, 3, 4, 5].map(id => used(id, ['pollo'], 2)), {
        ingredients_total: 2,
        best_match_count: 1,
        has_more: true,
      })
    );
    await settle(first);
    first.destroy(); // como al abrir una receta y regresar

    const second = TestBed.createComponent(HaveIngredientsComponent);
    second.detectChanges();
    const el = second.nativeElement as HTMLElement;
    expect(Array.from(el.querySelectorAll('.tag-input .ing')).map(i => i.textContent?.replace('×', '').trim())).toEqual(['pollo', 'arroz']);
    expect(el.querySelector<HTMLInputElement>('#fewest-extras')!.checked).toBe(false);
    expect(el.querySelectorAll('a.rcard').length).toBe(5);
    expect(button(el, 'Buscar más opciones')).toBeDefined();
    http.expectNone(r => r.url.endsWith('/recommendations/by-ingredients'));
  });

  it('con alergias que descartan la página pide la siguiente hasta juntar recetas', async () => {
    localStorage.setItem('chefwise.allergies', JSON.stringify({ presets: [], custom: ['cilantro'] }));
    const fixture = TestBed.createComponent(HaveIngredientsComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    addIngredients(fixture, ['pollo']);
    button(el, 'Buscar qué puedo cocinar').click();

    const withCilantro = (id: number) => used(id, ['pollo'], 1);
    const bad = [1, 2, 3, 4, 5].map(id => ({ ...withCilantro(id), ingredients: ['1 ramo de cilantro'] }));
    request().flush(recommendationsResponse(bad, { ingredients_total: 1, best_match_count: 1, has_more: true }));
    await fixture.whenStable();

    const second = request();
    expect(second.request.body).toMatchObject({ offset: 5 });
    second.flush(
      recommendationsResponse([6, 7, 8, 9, 10].map(withCilantro), { ingredients_total: 1, best_match_count: 1, has_more: true })
    );
    await settle(fixture);
    expect(el.querySelectorAll('a.rcard').length).toBe(5);
  });
});
