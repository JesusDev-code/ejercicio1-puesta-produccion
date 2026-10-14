import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Sesion } from './sesion';

// Las guardas solo deciden qué pantalla se pinta. Quien autoriza es la API: un usuario que
// fuerce la ruta /usuarios verá la pantalla vacía y un 403 en cada llamada.

export const requiereSesion: CanActivateFn = () =>
  inject(Sesion).autenticado() || inject(Router).createUrlTree(['/login']);

export const soloInvitados: CanActivateFn = () =>
  !inject(Sesion).autenticado() || inject(Router).createUrlTree(['/incidentes']);

export const soloAdmin: CanActivateFn = () =>
  inject(Sesion).esAdmin() || inject(Router).createUrlTree(['/incidentes']);
