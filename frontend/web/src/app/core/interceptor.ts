import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { Sesion } from './sesion';

/** Rutas públicas: ni llevan token ni un 401 en ellas significa «sesión caducada». */
const PUBLICAS = ['/api/salud', '/api/config/cliente'];

/**
 * Añade el ID token de Firebase a las llamadas a la API y gestiona el 401: se pide a Firebase
 * un token nuevo y se repite la petición una vez; si vuelve a fallar, se cierra la sesión y se
 * vuelve al login.
 *
 * En /api/auth/* el 401 es la respuesta final (p. ej. una cuenta dada de baja al entrar): se
 * devuelve tal cual, sin redirigir.
 */
export const interceptorApi: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/') || PUBLICAS.includes(req.url)) {
    return next(req);
  }

  const sesion = inject(Sesion);
  const router = inject(Router);
  const enviar = (r: HttpRequest<unknown>, forzar: boolean) =>
    from(sesion.token(forzar)).pipe(
      switchMap((token) => next(token ? r.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : r)),
    );
  const es401 = (e: unknown) => e instanceof HttpErrorResponse && e.status === 401;

  return enviar(req, false).pipe(
    catchError((error: unknown) => {
      if (!es401(error) || req.url.startsWith('/api/auth/')) {
        return throwError(() => error);
      }
      return enviar(req, true).pipe(
        catchError((otro: unknown) => {
          if (es401(otro)) {
            sesion.limpiar();
            void router.navigate(['/login'], { queryParams: { caducada: 1 } });
          }
          return throwError(() => otro);
        }),
      );
    }),
  );
};
