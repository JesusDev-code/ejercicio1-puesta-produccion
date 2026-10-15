import { NavigationError } from '@angular/router';

/**
 * Pestañas abiertas durante un despliegue.
 *
 * Cada build cambia el hash de los chunks y el despliegue borra los anteriores. Una pestaña
 * que cargó el build viejo, al navegar a una pantalla que aún no había abierto, pide un chunk
 * que ya no existe: el import falla y el router cancela la navegación sin decir nada. La salida
 * es una recarga completa hacia el destino (index.html va con no-store, así que trae el build
 * nuevo) y la sesión se recupera sola con la cookie de refresco.
 */

/** Una página recién cargada que ya falla no se recarga otra vez: un despliegue roto no hace bucle. */
const MINIMO_ABIERTA_MS = 5_000;

/** Error de carga de un módulo dinámico (Chromium, Firefox y Safari lo dicen distinto). */
export function esChunkDesaparecido(error: unknown): boolean {
  const texto = error instanceof Error ? `${error.name} ${error.message}` : String(error);
  return /dynamically imported module|importing a module script failed|module script|chunkloaderror/i.test(
    texto,
  );
}

export function recargarSiVersionVieja(
  evento: NavigationError,
  abiertaMs: number = performance.now(),
  ir: (url: string) => void = (url) => location.assign(url),
): void {
  if (esChunkDesaparecido(evento.error) && abiertaMs > MINIMO_ABIERTA_MS) {
    ir(evento.url);
  }
}
