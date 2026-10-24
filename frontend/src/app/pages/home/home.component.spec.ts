import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { itemDto, recommendationsResponse } from '../../testing/api-fixtures';
import { HomeComponent } from './home.component';

describe('HomeComponent (búsqueda del catálogo)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const ids = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => from + i);

  async function search(fixture: ReturnType<typeof TestBed.createComponent<HomeComponent>>, term: string) {
    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector<HTMLInputElement>('input')!;
    input.value = term;
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    el.querySelector<HTMLButtonElement>('.search-button')!.click();
  }

  async function settle(fixture: ReturnType<typeof TestBed.createComponent<HomeComponent>>) {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('ya no muestra la sección de categorías ni pide metadata', () => {
    const fixture = TestBed.createComponent(HomeComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).not.toContain('Categorías');
    expect(el.querySelector('.chip')).toBeNull();
    http.expectNone(r => r.url.endsWith('/metadata'));
  });

  it('muestra cinco resultados y cuántas coincidencias hay en total', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await search(fixture, 'tacos');

    const req = http.expectOne(r => r.url.endsWith('/recipes/search'));
    expect(req.request.params.get('q')).toBe('tacos');
    expect(req.request.params.get('top_n')).toBe('5');
    expect(req.request.params.has('offset')).toBe(false);
    req.flush(recommendationsResponse(ids(1, 5).map(id => itemDto(id)), { candidates: 42, has_more: true }));
    await settle(fixture);

    expect(el.querySelectorAll('a.recipe-item').length).toBe(5);
    expect(el.textContent).toContain('Resultados de búsqueda');
    expect(el.querySelector('.results-count')?.textContent).toContain('42 coincidencias con «tacos»');
  });

  it('con más de cinco coincidencias "Ver más recetas" agrega las siguientes', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await search(fixture, 'tacos');
    http
      .expectOne(r => r.url.endsWith('/recipes/search'))
      .flush(recommendationsResponse(ids(1, 5).map(id => itemDto(id)), { candidates: 8, has_more: true }));
    await settle(fixture);

    const more = el.querySelector<HTMLButtonElement>('.more-btn')!;
    expect(more.textContent).toContain('Ver más recetas');
    more.click();
    const req = http.expectOne(r => r.url.endsWith('/recipes/search'));
    expect(req.request.params.get('offset')).toBe('5');
    expect(req.request.params.get('q')).toBe('tacos');
    req.flush(recommendationsResponse(ids(6, 8).map(id => itemDto(id)), { candidates: 8, has_more: false }));
    await settle(fixture);

    expect(el.querySelectorAll('a.recipe-item').length).toBe(8);
    expect(el.querySelector('.more-btn')).toBeNull();
  });

  it('con cinco o menos coincidencias no ofrece buscar más', async () => {
    const fixture = TestBed.createComponent(HomeComponent);
    const el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
    await search(fixture, 'tacos');
    http
      .expectOne(r => r.url.endsWith('/recipes/search'))
      .flush(recommendationsResponse(ids(1, 1).map(id => itemDto(id)), { candidates: 1, has_more: false }));
    await settle(fixture);

    expect(el.querySelector('.more-btn')).toBeNull();
    expect(el.querySelector('.results-count')?.textContent).toContain('1 coincidencia con');
  });

  it('al volver a Inicio conserva lo buscado y sus resultados', async () => {
    const first = TestBed.createComponent(HomeComponent);
    first.detectChanges();
    await search(first, 'tacos');
    http
      .expectOne(r => r.url.endsWith('/recipes/search'))
      .flush(recommendationsResponse(ids(1, 5).map(id => itemDto(id)), { candidates: 9, has_more: true }));
    await settle(first);
    first.destroy(); // como al abrir una receta y regresar

    const second = TestBed.createComponent(HomeComponent);
    second.detectChanges();
    const el = second.nativeElement as HTMLElement;
    expect(el.querySelector<HTMLInputElement>('input')!.value).toBe('tacos');
    expect(el.querySelectorAll('a.recipe-item').length).toBe(5);
    expect(el.querySelector('.results-count')?.textContent).toContain('9 coincidencias');
    expect(el.querySelector('.more-btn')).not.toBeNull();
    http.expectNone(r => r.url.endsWith('/recipes/search'));
  });
});
