import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';

import { Sesion } from './sesion';

/**
 * Añade el Bearer a las llamadas a la API y gestiona el 401:
 * primero un refresco silencioso y se repite la petición una vez; si el refresco falla,
 * se borra la sesión y se vuelve al login.
 *
 * Las rutas /api/auth/* no llevan Bearer ni se reintentan: un 401 ahí es la respuesta final.
 */
export const interceptorApi: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/') || req.url.startsWith('/api/auth/')) {
    return next(req);
  }

  const sesion = inject(Sesion);
  const router = inject(Router);
  const conToken = (r: HttpRequest<unknown>) => {
    const token = sesion.tokenAcceso();
    return token ? r.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : r;
  };

  return next(conToken(req)).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401) {
        return throwError(() => error);
      }
      return sesion.refrescar().pipe(
        catchError(() => {
          sesion.limpiar();
          void router.navigate(['/login'], { queryParams: { caducada: 1 } });
          return throwError(() => error);
        }),
        switchMap(() => next(conToken(req))),
      );
    }),
  );
};
