import { inject } from '@angular/core';
import { CanActivateFn, CanMatchFn, Router } from '@angular/router';

import { Sesion } from './sesion';

// Las guardas solo deciden qué pantalla se pinta. Quien autoriza es la API: un usuario que
// fuerce la ruta /usuarios verá la pantalla vacía y un 403 en cada llamada.

export const requiereSesion: CanActivateFn = () =>
  inject(Sesion).autenticado() || inject(Router).createUrlTree(['/login']);

export const soloInvitados: CanActivateFn = () =>
  !inject(Sesion).autenticado() || inject(Router).createUrlTree(['/incidentes']);

/** canMatch: la ruta solo existe para quien no ha entrado (la landing pública). */
export const sinSesion: CanMatchFn = () => !inject(Sesion).autenticado();

export const soloAdmin: CanActivateFn = () =>
  inject(Sesion).esAdmin() || inject(Router).createUrlTree(['/incidentes']);
