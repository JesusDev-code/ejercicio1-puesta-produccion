import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';

import { requiereSesion, sinSesion, soloAdmin, soloInvitados } from './guardas';
import { Sesion } from './sesion';

function con(autenticado: boolean, esAdmin = false) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      { provide: Sesion, useValue: { autenticado: signal(autenticado), esAdmin: signal(esAdmin) } },
    ],
  });
}

/** Ejecuta una guarda funcional en el contexto de inyección del TestBed. */
const ejecutar = (guarda: (...a: never[]) => unknown) =>
  TestBed.runInInjectionContext(() => (guarda as () => unknown)());

const destino = (r: unknown) => TestBed.inject(Router).serializeUrl(r as UrlTree);

describe('guardas', () => {
  it('requiereSesion deja pasar con sesión', () => {
    con(true);
    expect(ejecutar(requiereSesion)).toBe(true);
  });

  it('requiereSesion manda al login sin sesión', () => {
    con(false);
    expect(destino(ejecutar(requiereSesion))).toBe('/login');
  });

  it('soloInvitados manda a la raíz a quien ya entró', () => {
    con(true);
    expect(destino(ejecutar(soloInvitados))).toBe('/');
  });

  it('sinSesion (landing pública) solo casa sin sesión', () => {
    con(false);
    expect(ejecutar(sinSesion)).toBe(true);
    TestBed.resetTestingModule();
    con(true);
    expect(ejecutar(sinSesion)).toBe(false);
  });

  it('soloAdmin deja pasar a un admin', () => {
    con(true, true);
    expect(ejecutar(soloAdmin)).toBe(true);
  });

  it('soloAdmin manda a otro rol a sus incidencias', () => {
    con(true, false);
    expect(destino(ejecutar(soloAdmin))).toBe('/incidentes');
  });
});
