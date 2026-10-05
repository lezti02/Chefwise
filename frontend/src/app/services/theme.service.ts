import { DOCUMENT } from '@angular/common';
import { Injectable, computed, effect, inject, signal } from '@angular/core';

export type Theme = 'light' | 'dark';
const THEME_KEY = 'chefwise.theme';

/**
 * Modo claro / oscuro. Sin elección guardada se sigue al sistema
 * (`prefers-color-scheme`); al pulsar el botón se fija la elección y se recuerda.
 * Los colores viven en src/styles.scss y cambian con `data-theme` en <html>.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);
  private chosen = signal<Theme | null>(readStored());
  private systemDark = signal(this.doc.defaultView?.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);

  readonly theme = computed<Theme>(() => this.chosen() ?? (this.systemDark() ? 'dark' : 'light'));
  readonly isDark = computed(() => this.theme() === 'dark');

  constructor() {
    const query = this.doc.defaultView?.matchMedia?.('(prefers-color-scheme: dark)');
    query?.addEventListener?.('change', e => this.systemDark.set(e.matches));
    effect(() => this.doc.documentElement.setAttribute('data-theme', this.theme()));
  }

  toggle(): void {
    const next: Theme = this.isDark() ? 'light' : 'dark';
    this.chosen.set(next);
    try {
      globalThis.localStorage?.setItem(THEME_KEY, next);
    } catch {
      /* almacenamiento bloqueado: el tema solo dura la sesión */
    }
  }
}

function readStored(): Theme | null {
  try {
    const value = globalThis.localStorage?.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}
