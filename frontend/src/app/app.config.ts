import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withNavigationErrorHandler } from '@angular/router';

import { routes } from './app.routes';
import { interceptorApi } from './core/interceptor';
import { Sesion } from './core/sesion';
import { recargarSiVersionVieja } from './core/version';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Tras un despliegue, una pestaña abierta con el build viejo recarga en vez de quedarse muda
    provideRouter(routes, withComponentInputBinding(), withNavigationErrorHandler((e) => recargarSiVersionVieja(e))),
    provideHttpClient(withFetch(), withInterceptors([interceptorApi])),
    // Antes de pintar nada: si la cookie de refresco sigue viva, se recupera la sesión
    provideAppInitializer(() => inject(Sesion).restaurar()),
  ],
};
