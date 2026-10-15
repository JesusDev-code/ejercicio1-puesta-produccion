import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';

import { interceptorApi } from './interceptor';
import { Sesion } from './sesion';

/** Deja que las promesas pendientes (el token de Firebase es asíncrono) se resuelvan. */
const tick = () => new Promise((r) => setTimeout(r));

describe('interceptorApi', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let sesion: { token: ReturnType<typeof vi.fn>; limpiar: ReturnType<typeof vi.fn> };
  let router: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    sesion = {
      token: vi.fn(async (forzar = false) => (forzar ? 'token-nuevo' : 'token-viejo')),
      limpiar: vi.fn(),
    };
    router = { navigate: vi.fn() };
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([interceptorApi])),
        provideHttpClientTesting(),
        { provide: Sesion, useValue: sesion },
        { provide: Router, useValue: router },
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => backend.verify());

  it('añade el ID token como Bearer a las llamadas a la API', async () => {
    const respuesta = firstValueFrom(http.get('/api/incidentes'));
    await tick();
    const req = backend.expectOne('/api/incidentes');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-viejo');
    req.flush({});
    await respuesta;
  });

  it.each(['/api/salud', '/api/config/cliente', '/assets/logo.svg'])(
    'no envía el token a %s',
    async (url) => {
      const respuesta = firstValueFrom(http.get(url));
      const req = backend.expectOne(url);
      expect(req.request.headers.has('Authorization')).toBe(false);
      req.flush({});
      await respuesta;
      expect(sesion.token).not.toHaveBeenCalled();
    },
  );

  it('ante un 401 pide un token nuevo a Firebase y repite una vez', async () => {
    const respuesta = firstValueFrom(http.get('/api/usuarios/yo'));
    await tick();
    backend.expectOne('/api/usuarios/yo').flush(null, { status: 401, statusText: 'No' });
    await tick();
    const reintento = backend.expectOne('/api/usuarios/yo');
    expect(sesion.token).toHaveBeenLastCalledWith(true);
    expect(reintento.request.headers.get('Authorization')).toBe('Bearer token-nuevo');
    reintento.flush({ id: 1 });
    expect(await respuesta).toEqual({ id: 1 });
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('si el reintento también da 401, cierra la sesión y vuelve al login', async () => {
    const respuesta = firstValueFrom(http.get('/api/usuarios/yo'));
    await tick();
    backend.expectOne('/api/usuarios/yo').flush(null, { status: 401, statusText: 'No' });
    await tick();
    backend.expectOne('/api/usuarios/yo').flush(null, { status: 401, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 401 });
    expect(sesion.limpiar).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/login'], { queryParams: { caducada: 1 } });
  });

  it('en /api/auth/* el 401 es la respuesta final: ni reintento ni redirección', async () => {
    const respuesta = firstValueFrom(http.post('/api/auth/sesion', null));
    await tick();
    backend.expectOne('/api/auth/sesion').flush(null, { status: 401, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 401 });
    expect(sesion.token).toHaveBeenCalledTimes(1);
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('otros errores pasan tal cual, sin reintento', async () => {
    const respuesta = firstValueFrom(http.get('/api/incidentes/9'));
    await tick();
    backend.expectOne('/api/incidentes/9').flush(null, { status: 404, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 404 });
    expect(sesion.token).toHaveBeenCalledTimes(1);
  });

  it('sin sesión no inventa cabecera', async () => {
    sesion.token.mockResolvedValue(null);
    const respuesta = firstValueFrom(http.get('/api/incidentes'));
    await tick();
    const req = backend.expectOne('/api/incidentes');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
    await respuesta;
  });
});
