import { aCodigo } from './clientes';

/** El patrón que exige la API para el código de un cliente (app/esquemas.py). */
const PATRON_API = /^[a-z0-9]+(-[a-z0-9]+)*$/;

describe('aCodigo (código sugerido de un cliente)', () => {
  it.each([
    ['Transportes Ibarra', 'transportes-ibarra'],
    ['Clínica Solana, S.L.', 'clinica-solana-s-l'],
    ['  Hotel   Mirador  ', 'hotel-mirador'],
    ['Ñandú & Cía', 'nandu-cia'],
    ['ACME 2026', 'acme-2026'],
  ])('«%s» → %s', (nombre, codigo) => {
    expect(aCodigo(nombre)).toBe(codigo);
  });

  it('nunca supera los 40 caracteres ni acaba en guion', () => {
    const codigo = aCodigo('Una empresa con un nombre larguísimo que no cabe en el código');
    expect(codigo.length).toBeLessThanOrEqual(40);
    expect(codigo.endsWith('-')).toBe(false);
  });

  it('lo que sugiere siempre lo acepta la API', () => {
    for (const nombre of ['Clínica Solana, S.L.', 'A--B', '¡Hola!', 'Über Café']) {
      expect(aCodigo(nombre)).toMatch(PATRON_API);
    }
  });
});
