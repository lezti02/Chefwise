import { provideZonelessChangeDetection } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { ThemeService } from './theme.service';

describe('ThemeService (modo oscuro)', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    TestBed.configureTestingModule({ providers: [provideZonelessChangeDetection()] });
  });

  it('alterna entre claro y oscuro, lo aplica a <html> y lo recuerda', () => {
    const theme = TestBed.inject(ThemeService);
    TestBed.tick();
    const start = theme.theme();
    const other = start === 'dark' ? 'light' : 'dark';

    theme.toggle();
    TestBed.tick();
    expect(theme.theme()).toBe(other);
    expect(document.documentElement.getAttribute('data-theme')).toBe(other);
    expect(localStorage.getItem('chefwise.theme')).toBe(other);

    theme.toggle();
    TestBed.tick();
    expect(document.documentElement.getAttribute('data-theme')).toBe(start);
  });

  it('usa la elección guardada al arrancar', () => {
    localStorage.setItem('chefwise.theme', 'dark');
    const theme = TestBed.inject(ThemeService);
    TestBed.tick();
    expect(theme.isDark()).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});
