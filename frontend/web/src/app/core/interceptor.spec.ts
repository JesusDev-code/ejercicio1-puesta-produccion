import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, firstValueFrom, of, share, throwError } from 'rxjs';

import { interceptorApi } from './interceptor';
import { Sesion } from './sesion';

describe('interceptorApi', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let token: string | null;
  let sesion: {
    tokenAcceso: ReturnType<typeof vi.fn>;
    refrescar: ReturnType<typeof vi.fn>;
    limpiar: ReturnType<typeof vi.fn>;
  };
  let router: { navigate: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    token = 'token-viejo';
    sesion = {
      tokenAcceso: vi.fn(() => token),
      refrescar: vi.fn(() => {
        token = 'token-nuevo';
        return of('token-nuevo');
      }),
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

  it('añade el token de acceso como Bearer a las llamadas a la API', async () => {
    const respuesta = firstValueFrom(http.get('/api/incidentes'));
    const req = backend.expectOne('/api/incidentes');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-viejo');
    req.flush({});
    await respuesta;
  });

  it.each(['/api/auth/web/login', '/api/auth/web/refrescar', '/assets/logo.svg'])(
    'no envía el token a %s',
    async (url) => {
      const respuesta = firstValueFrom(http.post(url, null));
      const req = backend.expectOne(url);
      expect(req.request.headers.has('Authorization')).toBe(false);
      req.flush({});
      await respuesta;
      expect(sesion.tokenAcceso).not.toHaveBeenCalled();
    },
  );

  it('ante un 401 refresca en silencio y repite una vez con el token nuevo', async () => {
    const respuesta = firstValueFrom(http.get('/api/usuarios/yo'));
    backend.expectOne('/api/usuarios/yo').flush(null, { status: 401, statusText: 'No' });
    const reintento = backend.expectOne('/api/usuarios/yo');
    expect(sesion.refrescar).toHaveBeenCalledTimes(1);
    expect(reintento.request.headers.get('Authorization')).toBe('Bearer token-nuevo');
    reintento.flush({ id: 1 });
    expect(await respuesta).toEqual({ id: 1 });
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('si el refresco falla, cierra la sesión y vuelve al login', async () => {
    sesion.refrescar.mockReturnValue(throwError(() => new Error('cookie caducada')));
    const respuesta = firstValueFrom(http.get('/api/usuarios/yo'));
    backend.expectOne('/api/usuarios/yo').flush(null, { status: 401, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 401 });
    expect(sesion.limpiar).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/login'], { queryParams: { caducada: 1 } });
  });

  it('varios 401 a la vez esperan al mismo refresco (la cookie no se reutiliza)', async () => {
    // La Sesion real comparte el refresco en curso; el interceptor debe engancharse a él
    const enCurso = new Subject<string>();
    const compartido = enCurso.pipe(share());
    sesion.refrescar.mockReturnValue(compartido);

    const a = firstValueFrom(http.get('/api/incidentes'));
    const b = firstValueFrom(http.get('/api/eventos'));
    backend.expectOne('/api/incidentes').flush(null, { status: 401, statusText: 'No' });
    backend.expectOne('/api/eventos').flush(null, { status: 401, statusText: 'No' });

    token = 'token-nuevo';
    enCurso.next('token-nuevo');
    enCurso.complete();

    for (const url of ['/api/incidentes', '/api/eventos']) {
      const reintento = backend.expectOne(url);
      expect(reintento.request.headers.get('Authorization')).toBe('Bearer token-nuevo');
      reintento.flush([]);
    }
    await Promise.all([a, b]);
  });

  it('en /api/auth/* el 401 es la respuesta final: ni refresco ni redirección', async () => {
    const respuesta = firstValueFrom(http.post('/api/auth/web/login', {}));
    backend.expectOne('/api/auth/web/login').flush(null, { status: 401, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 401 });
    expect(sesion.refrescar).not.toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('otros errores pasan tal cual, sin refresco', async () => {
    const respuesta = firstValueFrom(http.get('/api/incidentes/9'));
    backend.expectOne('/api/incidentes/9').flush(null, { status: 404, statusText: 'No' });
    await expect(respuesta).rejects.toMatchObject({ status: 404 });
    expect(sesion.refrescar).not.toHaveBeenCalled();
  });

  it('sin sesión no inventa cabecera', async () => {
    token = null;
    const respuesta = firstValueFrom(http.get('/api/incidentes'));
    const req = backend.expectOne('/api/incidentes');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
    await respuesta;
  });
});
