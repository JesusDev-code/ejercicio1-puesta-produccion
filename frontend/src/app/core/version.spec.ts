import { NavigationError } from '@angular/router';
import { describe, expect, it, vi } from 'vitest';

import { esChunkDesaparecido, recargarSiVersionVieja } from './version';

const fallo = (error: unknown) => new NavigationError(1, '/clientes', error);

describe('version', () => {
  it.each([
    new TypeError('Failed to fetch dynamically imported module: https://x/chunk-ABC.js'),
    new TypeError('Importing a module script failed.'),
    new Error("Failed to load module script: Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of 'text/html'"),
  ])('reconoce un chunk que ya no existe: %s', (error) => {
    expect(esChunkDesaparecido(error)).toBe(true);
  });

  it('no confunde otros errores de navegación con un despliegue', () => {
    expect(esChunkDesaparecido(new Error('Cannot match any routes'))).toBe(false);
  });

  it('recarga hacia el destino que se pidió', () => {
    const ir = vi.fn();
    recargarSiVersionVieja(fallo(new TypeError('Failed to fetch dynamically imported module')), 60_000, ir);
    expect(ir).toHaveBeenCalledWith('/clientes');
  });

  it('no recarga una página recién cargada: un despliegue roto no entra en bucle', () => {
    const ir = vi.fn();
    recargarSiVersionVieja(fallo(new TypeError('Failed to fetch dynamically imported module')), 1_000, ir);
    expect(ir).not.toHaveBeenCalled();
  });

  it('no recarga por un error que no es de carga', () => {
    const ir = vi.fn();
    recargarSiVersionVieja(fallo(new Error('otro fallo')), 60_000, ir);
    expect(ir).not.toHaveBeenCalled();
  });
});
