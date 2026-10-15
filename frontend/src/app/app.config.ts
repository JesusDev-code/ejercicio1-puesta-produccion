import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';

import { routes } from './app.routes';
import { interceptorApi } from './core/interceptor';
import { Sesion } from './core/sesion';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch(), withInterceptors([interceptorApi])),
    // Antes de pintar nada: si la cookie de refresco sigue viva, se recupera la sesión
    provideAppInitializer(() => inject(Sesion).restaurar()),
  ],
};
