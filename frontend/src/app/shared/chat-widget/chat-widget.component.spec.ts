import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ChatWidgetComponent } from './chat-widget.component';
import { ChatService } from '../../services/chat.service';

describe('ChatWidgetComponent', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  async function render() {
    const fixture = TestBed.createComponent(ChatWidgetComponent);
    const component = fixture.componentInstance;
    const el = fixture.nativeElement as HTMLElement;
    await fixture.whenStable();
    fixture.detectChanges();
    return { fixture, component, el };
  }

  it('muestra el globo de presentación del ayudante de chef y permite cerrarlo', async () => {
    const { fixture, component, el } = await render();

    expect(component.showCallout()).toBe(true);
    const callout = el.querySelector<HTMLElement>('.chat-callout');
    expect(callout).toBeTruthy();
    expect(callout?.textContent).toContain('ayudante de chef');

    const closeBtn = el.querySelector<HTMLButtonElement>('.callout-close')!;
    closeBtn.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(component.showCallout()).toBe(false);
    expect(localStorage.getItem('chefwise_callout_dismissed')).toBe('true');
    expect(el.querySelector('.chat-callout')).toBeFalsy();
  });

  it('hacer clic en el globo abre el chat', async () => {
    const { fixture, component, el } = await render();
    const chatService = TestBed.inject(ChatService);

    expect(chatService.isOpen()).toBe(false);
    const callout = el.querySelector<HTMLElement>('.chat-callout')!;
    callout.click();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(chatService.isOpen()).toBe(true);
    expect(el.querySelector('.chat-panel')).toBeTruthy();
  });

  it('un clic en el botón flotante alterna la apertura del chat', async () => {
    const { fixture, component, el } = await render();
    const chatService = TestBed.inject(ChatService);
    const fab = el.querySelector<HTMLButtonElement>('.fab-chat')!;

    // Simular puntero sin desplazamiento (click limpio)
    fab.dispatchEvent(new PointerEvent('pointerdown', { button: 0, clientX: 100, clientY: 100 }));
    fab.dispatchEvent(new PointerEvent('pointerup', { button: 0, clientX: 100, clientY: 100 }));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(chatService.isOpen()).toBe(true);
    expect(el.querySelector('.chat-panel')).toBeTruthy();

    fab.dispatchEvent(new PointerEvent('pointerdown', { button: 0, clientX: 100, clientY: 100 }));
    fab.dispatchEvent(new PointerEvent('pointerup', { button: 0, clientX: 100, clientY: 100 }));
    await fixture.whenStable();
    fixture.detectChanges();

    expect(chatService.isOpen()).toBe(false);
  });

  it('arrastrar el botón flotante actualiza la posición y no abre el chat', async () => {
    const { fixture, component, el } = await render();
    const chatService = TestBed.inject(ChatService);
    const fab = el.querySelector<HTMLButtonElement>('.fab-chat')!;

    fab.dispatchEvent(new PointerEvent('pointerdown', { button: 0, clientX: 200, clientY: 300 }));
    fab.dispatchEvent(new PointerEvent('pointermove', { clientX: 250, clientY: 380 }));
    fab.dispatchEvent(new PointerEvent('pointerup', { button: 0, clientX: 250, clientY: 380 }));
    await fixture.whenStable();
    fixture.detectChanges();

    // No debe alternar el estado de apertura al arrastrar
    expect(chatService.isOpen()).toBe(false);

    // La posición debe haberse asignado y persistido
    const pos = component.position();
    expect(pos).not.toBeNull();
    expect(localStorage.getItem('chefwise_chat_pos')).toBeTruthy();
  });
});
