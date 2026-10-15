import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';

import {
  conEmpresa,
  requiereSesion,
  sinSesion,
  soloAdmin,
  soloGestor,
  soloInvitados,
  soloPendientes,
} from './guardas';
import { Sesion } from './sesion';

function con(autenticado: boolean, esAdmin = false, extra: { esGestor?: boolean; pendiente?: boolean } = {}) {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      {
        provide: Sesion,
        useValue: {
          autenticado: signal(autenticado),
          esAdmin: signal(esAdmin),
          esGestor: signal(extra.esGestor ?? false),
          pendiente: signal(extra.pendiente ?? false),
        },
      },
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

  it('soloGestor deja pasar al gestor y manda al resto a sus incidencias', () => {
    con(true, false, { esGestor: true });
    expect(ejecutar(soloGestor)).toBe(true);
    TestBed.resetTestingModule();
    con(true, true);
    expect(destino(ejecutar(soloGestor))).toBe('/incidentes');
  });

  it('conEmpresa saca de la consola a una cuenta pendiente', () => {
    con(true, false, { pendiente: true });
    expect(destino(ejecutar(conEmpresa))).toBe('/unirse');
    TestBed.resetTestingModule();
    con(true, false);
    expect(ejecutar(conEmpresa)).toBe(true);
  });

  it('soloPendientes: «Unirme a mi empresa» no es para quien ya tiene empresa', () => {
    con(true, false, { pendiente: true });
    expect(ejecutar(soloPendientes)).toBe(true);
    TestBed.resetTestingModule();
    con(true, true);
    expect(destino(ejecutar(soloPendientes))).toBe('/');
  });
});
