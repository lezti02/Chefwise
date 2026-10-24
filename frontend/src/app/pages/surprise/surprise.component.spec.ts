import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { SurpriseComponent } from './surprise.component';
import { itemDto, recommendationsResponse } from '../../testing/api-fixtures';

describe('SurpriseComponent (consume la API real)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const nextRequest = (): TestRequest => http.expectOne(r => r.url.endsWith('/recommendations'));

  async function render(tags = ['Comida rápida', 'Picante']) {
    const fixture = TestBed.createComponent(SurpriseComponent);
    const el = fixture.nativeElement as HTMLElement;
    http.expectOne(r => r.url.endsWith('/metadata')).flush({ tags, countries: ['México', 'Perú'] });
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, el };
  }

  it('pide recomendaciones al backend con los controles por defecto y pinta tarjetas reales', async () => {
    const { fixture, el } = await render();

    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    const req = nextRequest();
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      tags: [],
      difficulty: 'facil',
      max_time: 30,
      countries: [],
      exclude_ids: [],
      top_n: 5,
    });
    req.flush(recommendationsResponse([itemDto(101, { name: 'Pasta rápida' }), itemDto(102, { name: 'Sopa de fideo' })]));
    await fixture.whenStable();
    fixture.detectChanges();

    const cards = Array.from(el.querySelectorAll('a.rcard'));
    expect(cards.length).toBe(2);
    expect(cards.map(c => c.querySelector('.name')?.textContent?.trim())).toEqual(['Pasta rápida', 'Sopa de fideo']);
    // Click en la tarjeta => /receta/<recipe_id real>
    expect(cards[0].getAttribute('href')).toBe('/receta/101');
  });

  it('"Aplicar filtros" manda el estado actual de los controles', async () => {
    const { fixture, el } = await render();

    const chip = (text: string) =>
      Array.from(el.querySelectorAll<HTMLElement>('.chip')).find(c => c.textContent?.trim() === text)!;
    chip('Picante').click();
    chip('Intermedio').click();
    const slider = el.querySelector<HTMLInputElement>('input[type="range"]')!;
    slider.value = '35';
    slider.dispatchEvent(new Event('input')); // arrastrar la barra => 35 min
    fixture.detectChanges();
    expect(el.querySelector('label[for="max-minutes"]')?.textContent).toContain('35 min');

    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();

    const req = nextRequest();
    expect(req.request.body).toMatchObject({
      tags: ['Picante'],
      difficulty: 'intermedio',
      max_time: 35,
    });
    req.flush(recommendationsResponse([itemDto(7, { name: 'Chilaquiles' })]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('a.rcard .name')?.textContent?.trim()).toBe('Chilaquiles');
  });

  it('"el que sea" quita el límite de tiempo de preparación', async () => {
    const { fixture, el } = await render();
    const toggle = el.querySelector<HTMLInputElement>('#any-time')!;
    toggle.checked = true;
    toggle.dispatchEvent(new Event('change'));
    fixture.detectChanges();

    expect(el.querySelector<HTMLInputElement>('#max-minutes')!.disabled).toBe(true);
    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    const req = nextRequest();
    expect(req.request.body.max_time).toBeNull();
    req.flush(recommendationsResponse([]));
  });

  it('con los mismos controles, "ideas nuevas" excluye lo ya mostrado', async () => {
    const { fixture, el } = await render();
    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    nextRequest().flush(recommendationsResponse([itemDto(1), itemDto(2)]));
    await fixture.whenStable();
    fixture.detectChanges();

    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    const req = nextRequest();
    expect(req.request.body.exclude_ids.sort()).toEqual([1, 2]);
    req.flush(recommendationsResponse([itemDto(3)]));
  });

  it('manda favoritas y vistas para personalizar el ranking', async () => {
    localStorage.setItem(
      'chefwise.recipeState',
      JSON.stringify({ '88': { isFavorite: true, isSaved: false, lastCookedAt: null } })
    );
    localStorage.setItem('chefwise.recentViews', JSON.stringify(['42', '88']));
    const { el } = await render();
    expect(el.textContent).toContain('favorito o cocinado');
    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    const req = nextRequest();
    expect(req.request.body.favorite_ids).toEqual([88]);
    expect(req.request.body.viewed_ids).toEqual([42, 88]);
    req.flush(recommendationsResponse([itemDto(3)]));
  });

  it('muestra un mensaje claro si el backend no responde', async () => {
    const { fixture, el } = await render();
    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    nextRequest().flush('boom', { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(el.querySelectorAll('a.rcard').length).toBe(0);
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('backend');
  });

  it('al volver a la pantalla conserva filtros y recetas mostradas', async () => {
    const first = await render();
    const chip = (el: HTMLElement, text: string) =>
      Array.from(el.querySelectorAll<HTMLElement>('.chip')).find(c => c.textContent?.trim() === text)!;
    chip(first.el, 'Picante').click();
    const slider = first.el.querySelector<HTMLInputElement>('input[type="range"]')!;
    slider.value = '60';
    slider.dispatchEvent(new Event('input'));
    first.fixture.detectChanges();
    first.el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    nextRequest().flush(recommendationsResponse([itemDto(7, { name: 'Chilaquiles' })]));
    await first.fixture.whenStable();
    first.fixture.detectChanges();
    first.fixture.destroy(); // como al abrir una receta y navegar fuera

    const second = await render();
    expect(chip(second.el, 'Picante').classList).toContain('on');
    expect(second.el.querySelector('label[for="max-minutes"]')?.textContent).toContain('60 min');
    expect(second.el.querySelector('a.rcard .name')?.textContent?.trim()).toBe('Chilaquiles');
  });
});
