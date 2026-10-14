import { HttpErrorResponse } from '@angular/common/http';

export function codigo(error: unknown): number {
  return error instanceof HttpErrorResponse ? error.status : 0;
}

/** Mensaje de la API (`detail` de tipo texto). Nunca trazas: la API ya no las envía. */
export function detalle(error: unknown): string | null {
  if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') {
    return error.error.detail;
  }
  return null;
}

/** Campos señalados por un 422 de FastAPI: `detail: [{ loc: ['body', 'titulo'], ... }]`. */
export function camposInvalidos(error: unknown): Set<string> {
  const campos = new Set<string>();
  if (error instanceof HttpErrorResponse && error.status === 422 && Array.isArray(error.error?.detail)) {
    for (const item of error.error.detail) {
      const campo = item?.loc?.at(-1);
      if (typeof campo === 'string') campos.add(campo);
    }
  }
  return campos;
}

/** Texto genérico para los códigos que se tratan igual en todas las pantallas. */
export function mensajeGeneral(error: unknown): string {
  switch (codigo(error)) {
    case 0:
      return 'No hay conexión con la API.';
    case 403:
      return 'No tienes permiso para esta acción.';
    case 404:
      return 'No existe.';
    case 409:
      return detalle(error) ?? 'El cambio entra en conflicto con el estado actual.';
    case 429:
      return 'Demasiadas peticiones. Espera un minuto antes de volver a probar.';
    default:
      return codigo(error) >= 500 ? 'Algo ha fallado en el servidor.' : (detalle(error) ?? 'Petición no válida.');
  }
}
