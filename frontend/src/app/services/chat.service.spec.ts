import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { ChatService } from './chat.service';
import { RecipeService } from './recipe.service';

describe('ChatService (POST /chat)', () => {
  let http: HttpTestingController;
  let chat: ChatService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    chat = TestBed.inject(ChatService);
  });

  afterEach(() => http.verify());

  it('envía la pregunta con la receta abierta, las visibles y las alergias del usuario', () => {
    TestBed.inject(RecipeService).togglePresetAllergy('lacteos');
    chat.setFocusRecipe({ id: '19', name: 'Tacos de pescado' });
    chat.setVisibleRecipes([{ id: '7', name: 'Sopa' }]);

    chat.ask('¿Con qué sustituyo la crema?');
    expect(chat.pending()).toBe(true);

    const req = http.expectOne(r => r.url.endsWith('/chat'));
    expect(req.request.body).toEqual({
      message: '¿Con qué sustituyo la crema?',
      history: [expect.objectContaining({ role: 'bot' })], // saludo inicial
      recipe_id: 19,
      visible_recipe_ids: [7],
      allergies: ['Lácteos'],
      current_step: null,
    });
    req.flush({ reply: 'Usa yogur griego.' });

    expect(chat.pending()).toBe(false);
    expect(chat.messages().at(-1)).toEqual({ role: 'bot', text: 'Usa yogur griego.' });
    expect(chat.contextLabel()).toBe('Tacos de pescado');
  });

  it('muestra el mensaje seguro del backend cuando el asistente no está disponible', () => {
    chat.ask('Hola');
    http
      .expectOne(r => r.url.endsWith('/chat'))
      .flush({ detail: 'El asistente alcanzó su límite de uso gratuito.' }, { status: 503, statusText: 'Unavailable' });
    expect(chat.messages().at(-1)?.text).toBe('El asistente alcanzó su límite de uso gratuito.');
  });
});
