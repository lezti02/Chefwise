import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';

export interface ChatPosition {
  x: number;
  y: number;
}

/**
 * Chatbot flotante GLOBAL con soporte para arrastrar/mover por la pantalla
 * y globo de presentación del ayudante de cocina con IA.
 */
@Component({
  selector: 'app-chat-widget',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat-widget.component.html',
  styleUrl: './chat-widget.component.scss',
})
export class ChatWidgetComponent {
  expanded = signal(false);
  draft = '';
  showCallout = signal(true);
  position = signal<ChatPosition | null>(null);

  private isDragging = false;
  private dragOriginPointer = { x: 0, y: 0 };
  private dragOriginElement = { x: 0, y: 0 };
  private hasMoved = false;

  constructor(public chat: ChatService) {
    if (typeof window !== 'undefined') {
      try {
        const savedDismiss = localStorage.getItem('chefwise_callout_dismissed');
        if (savedDismiss === 'true') {
          this.showCallout.set(false);
        }
        const savedPos = localStorage.getItem('chefwise_chat_pos');
        if (savedPos) {
          const parsed = JSON.parse(savedPos);
          if (typeof parsed?.x === 'number' && typeof parsed?.y === 'number') {
            const clamped = this.clampPosition(parsed.x, parsed.y, 52, 52);
            this.position.set(clamped);
          }
        }
      } catch {}
    }
  }

  readonly fabStyle = computed(() => {
    const p = this.position();
    if (!p) return {};
    return {
      left: `${p.x}px`,
      top: `${p.y}px`,
      right: 'auto',
      bottom: 'auto',
    };
  });

  readonly panelStyle = computed(() => {
    const p = this.position();
    if (!p || typeof window === 'undefined') return {};
    const winW = window.innerWidth;
    const winH = window.innerHeight;
    const style: Record<string, string> = {};

    if (p.x >= winW / 2) {
      style['right'] = `${Math.max(12, winW - p.x - 52)}px`;
      style['left'] = 'auto';
    } else {
      style['left'] = `${Math.max(12, p.x)}px`;
      style['right'] = 'auto';
    }

    if (p.y >= 350) {
      style['bottom'] = `${Math.max(12, winH - p.y + 10)}px`;
      style['top'] = 'auto';
    } else {
      style['top'] = `${Math.max(12, p.y + 62)}px`;
      style['bottom'] = 'auto';
    }

    return style;
  });

  readonly calloutStyle = computed(() => {
    const p = this.position();
    if (!p || typeof window === 'undefined') return {};
    const winW = window.innerWidth;
    const winH = window.innerHeight;
    const style: Record<string, string> = {};

    if (p.x >= winW / 2) {
      style['right'] = `${Math.max(12, winW - p.x - 52)}px`;
      style['left'] = 'auto';
    } else {
      style['left'] = `${Math.max(12, p.x)}px`;
      style['right'] = 'auto';
    }

    if (p.y >= 160) {
      style['bottom'] = `${Math.max(12, winH - p.y + 8)}px`;
      style['top'] = 'auto';
    } else {
      style['top'] = `${Math.max(12, p.y + 60)}px`;
      style['bottom'] = 'auto';
    }

    return style;
  });

  private clampPosition(x: number, y: number, w: number, h: number): ChatPosition {
    const pad = 12;
    const maxX = Math.max(pad, (typeof window !== 'undefined' ? window.innerWidth : 1024) - w - pad);
    const maxY = Math.max(pad, (typeof window !== 'undefined' ? window.innerHeight : 768) - h - pad);
    return {
      x: Math.max(pad, Math.min(maxX, x)),
      y: Math.max(pad, Math.min(maxY, y)),
    };
  }

  onFabPointerDown(event: PointerEvent): void {
    if (event.button !== 0) return;
    const target = event.currentTarget as HTMLElement;
    try {
      target.setPointerCapture?.(event.pointerId);
    } catch {}

    const rect = target.getBoundingClientRect();
    this.isDragging = true;
    this.hasMoved = false;
    this.dragOriginPointer = { x: event.clientX, y: event.clientY };
    this.dragOriginElement = { x: rect.left, y: rect.top };
  }

  onFabPointerMove(event: PointerEvent): void {
    if (!this.isDragging) return;
    const dx = event.clientX - this.dragOriginPointer.x;
    const dy = event.clientY - this.dragOriginPointer.y;

    if (!this.hasMoved && Math.hypot(dx, dy) > 5) {
      this.hasMoved = true;
    }

    if (this.hasMoved) {
      const clamped = this.clampPosition(this.dragOriginElement.x + dx, this.dragOriginElement.y + dy, 52, 52);
      this.position.set(clamped);
    }
  }

  onFabPointerUp(event: PointerEvent): void {
    if (!this.isDragging) return;
    this.isDragging = false;
    const target = event.currentTarget as HTMLElement;
    try {
      target.releasePointerCapture?.(event.pointerId);
    } catch {}

    if (this.hasMoved) {
      const p = this.position();
      if (p) {
        try {
          localStorage.setItem('chefwise_chat_pos', JSON.stringify(p));
        } catch {}
      }
    } else {
      this.toggleOpen();
    }
  }

  toggleOpen(): void {
    this.chat.toggleChat();
  }

  close(): void {
    this.chat.closeChat();
    this.expanded.set(false);
  }

  dismissCallout(event: Event): void {
    event.stopPropagation();
    this.showCallout.set(false);
    try {
      localStorage.setItem('chefwise_callout_dismissed', 'true');
    } catch {}
  }

  openFromCallout(): void {
    this.chat.openChat();
  }

  send(): void {
    if (!this.draft.trim() || this.chat.pending()) return;
    this.expanded.set(true);
    this.chat.ask(this.draft);
    this.draft = '';
  }
}
