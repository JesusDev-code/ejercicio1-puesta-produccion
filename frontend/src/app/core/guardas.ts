import { inject } from '@angular/core';
import { CanActivateFn, CanMatchFn, Router } from '@angular/router';

import { Sesion } from './sesion';

// Las guardas solo deciden qué pantalla se pinta. Quien autoriza es la API: un usuario que
// fuerce la ruta /usuarios verá la pantalla vacía y un 403 en cada llamada.

export const requiereSesion: CanActivateFn = () =>
  inject(Sesion).autenticado() || inject(Router).createUrlTree(['/login']);

export const soloInvitados: CanActivateFn = () =>
  !inject(Sesion).autenticado() || inject(Router).createUrlTree(['/']);

/** canMatch: la ruta solo existe para quien no ha entrado (la landing pública). */
export const sinSesion: CanMatchFn = () => !inject(Sesion).autenticado();

export const soloAdmin: CanActivateFn = () =>
  inject(Sesion).esAdmin() || inject(Router).createUrlTree(['/incidentes']);

export const soloGestor: CanActivateFn = () =>
  inject(Sesion).esGestor() || inject(Router).createUrlTree(['/incidentes']);

/** La consola: una cuenta pendiente (sin empresa) va a «Unirme a mi empresa». */
export const conEmpresa: CanActivateFn = () =>
  !inject(Sesion).pendiente() || inject(Router).createUrlTree(['/unirse']);

/** La consola: el personal que aún no tiene MFA va primero a activarlo. */
export const conMfa: CanActivateFn = () =>
  !inject(Sesion).mfaPorActivar() || inject(Router).createUrlTree(['/activar-mfa']);

/** «Activar MFA»: solo para quien lo tiene pendiente; los demás, a su consola. */
export const soloMfaPorActivar: CanActivateFn = () =>
  inject(Sesion).mfaPorActivar() || inject(Router).createUrlTree(['/']);

/** «Unirme a mi empresa»: solo para cuentas pendientes; las demás, a su consola. */
export const soloPendientes: CanActivateFn = () =>
  inject(Sesion).pendiente() || inject(Router).createUrlTree(['/']);
