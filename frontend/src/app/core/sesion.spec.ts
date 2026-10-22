import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { Sesion } from './sesion';

const TOKEN = { token_acceso: 'acceso-1', tipo_token: 'bearer', expira_en_segundos: 900 };
const USUARIO = { id: 1, email: 'admin@kaelum.example.com', rol: 'admin' };

describe('Sesion', () => {
  let sesion: Sesion;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    sesion = TestBed.inject(Sesion);
    backend = TestBed.inject(HttpTestingController);
  });

  afterEach(() => backend.verify());

  it('al entrar guarda el token solo en memoria y carga el usuario', async () => {
    const entrada = sesion.entrar('admin@kaelum.example.com', 'x');
    const login = backend.expectOne('/api/auth/web/login');
    expect(login.request.body).toEqual({ email: 'admin@kaelum.example.com', contrasena: 'x' });
    login.flush(TOKEN);
    await Promise.resolve();
    backend.expectOne('/api/usuarios/yo').flush(USUARIO);
    await entrada;

    expect(sesion.tokenAcceso()).toBe('acceso-1');
    expect(sesion.esAdmin()).toBe(true);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it('con MFA, el primer paso no deja token: devuelve el desafío', async () => {
    const entrada = sesion.entrar('admin@kaelum.example.com', 'x');
    backend
      .expectOne('/api/auth/web/login')
      .flush({ mfa_requerido: true, desafio: 'desafio-1', expira_en_segundos: 300 });
    expect(await entrada).toBe('desafio-1');
    expect(sesion.tokenAcceso()).toBeNull();
    expect(sesion.autenticado()).toBe(false);
  });

  it('completar el MFA abre la sesión', async () => {
    const paso = sesion.completarMfa('desafio-1', '123456');
    const mfa = backend.expectOne('/api/auth/web/mfa');
    expect(mfa.request.body).toEqual({ desafio: 'desafio-1', codigo: '123456' });
    mfa.flush(TOKEN);
    await Promise.resolve();
    backend.expectOne('/api/usuarios/yo').flush(USUARIO);
    await paso;
    expect(sesion.tokenAcceso()).toBe('acceso-1');
    expect(sesion.autenticado()).toBe(true);
  });

  it('dos refrescos simultáneos hacen UNA sola petición', async () => {
    // Dos POST con la misma cookie serían una reutilización: la API revocaría la familia entera
    const a = firstValueFrom(sesion.refrescar());
    const b = firstValueFrom(sesion.refrescar());
    backend.expectOne('/api/auth/web/refrescar').flush({ ...TOKEN, token_acceso: 'acceso-2' });
    expect(await a).toBe('acceso-2');
    expect(await b).toBe('acceso-2');
    expect(sesion.tokenAcceso()).toBe('acceso-2');
  });

  it('terminado un refresco, el siguiente vuelve a ir a la API', async () => {
    const primero = firstValueFrom(sesion.refrescar());
    backend.expectOne('/api/auth/web/refrescar').flush(TOKEN);
    await primero;
    const segundo = firstValueFrom(sesion.refrescar());
    backend.expectOne('/api/auth/web/refrescar').flush({ ...TOKEN, token_acceso: 'acceso-3' });
    expect(await segundo).toBe('acceso-3');
  });

  it('restaurar sin cookie válida deja la sesión vacía', async () => {
    const restaurar = sesion.restaurar();
    backend.expectOne('/api/auth/web/refrescar').flush(null, { status: 401, statusText: 'No' });
    await restaurar;
    expect(sesion.autenticado()).toBe(false);
    expect(sesion.tokenAcceso()).toBeNull();
  });

  it('salir borra la sesión local aunque la API no responda', async () => {
    const salida = sesion.salir();
    backend.expectOne('/api/auth/web/logout').error(new ProgressEvent('error'));
    await salida;
    expect(sesion.tokenAcceso()).toBeNull();
    expect(sesion.usuario()).toBeNull();
  });
});
