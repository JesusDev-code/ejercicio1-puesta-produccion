import { TestBed } from '@angular/core/testing';

import { Api } from './api';
import { Clientes } from './clientes';
import { Empresa } from './modelos';

const empresa = (id: number, nombre: string, activa = true): Empresa => ({
  id,
  codigo: nombre.toLowerCase().replace(/\s+/g, '-'),
  nombre,
  sector: null,
  activa,
  codigo_invitacion: `ABCD-EFGH-JK${id}${id}`,
  creada_en: '2026-10-14T00:00:00Z',
});

describe('Clientes', () => {
  let clientes: Clientes;
  let api: { empresas: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    api = {
      empresas: vi.fn().mockResolvedValue({
        total: 2,
        limite: 100,
        desplazamiento: 0,
        elementos: [empresa(1, 'Clínica Solana'), empresa(2, 'Hotel Mirador', false)],
      }),
    };
    TestBed.configureTestingModule({ providers: [{ provide: Api, useValue: api }] });
    clientes = TestBed.inject(Clientes);
  });

  it('el personal propio (sin empresa) se muestra como Kaelum', () => {
    expect(clientes.nombre(null)).toBe('Kaelum');
  });

  it('traduce el id al nombre una vez cargados', async () => {
    await clientes.cargar();
    expect(clientes.nombre(1)).toBe('Clínica Solana');
  });

  it('un id desconocido no rompe la pantalla', () => {
    expect(clientes.nombre(99)).toBe('Cliente #99');
  });

  it('carga una sola vez aunque la pidan varias pantallas', async () => {
    await Promise.all([clientes.cargar(), clientes.cargar(), clientes.cargar()]);
    expect(api.empresas).toHaveBeenCalledTimes(1);
  });

  it('con forzar vuelve a pedirlos', async () => {
    await clientes.cargar();
    await clientes.cargar(true);
    expect(api.empresas).toHaveBeenCalledTimes(2);
  });

  it('si falla la carga, la siguiente llamada lo reintenta', async () => {
    api.empresas.mockRejectedValueOnce(new Error('403'));
    await clientes.cargar();
    await clientes.cargar();
    expect(api.empresas).toHaveBeenCalledTimes(2);
  });

  it('el filtro incluye «todos» y marca los clientes de baja', async () => {
    await clientes.cargar();
    expect(clientes.opcionesFiltro().map((o) => o.etiqueta)).toEqual([
      'Todos los clientes',
      'Clínica Solana',
      'Hotel Mirador (baja)',
    ]);
  });

  it('en un alta no se ofrecen los clientes de baja', async () => {
    await clientes.cargar();
    const valores = clientes.opcionesAlta().map((o) => o.valor);
    expect(valores).toEqual([null, 1]);
  });

  it('actualizar sustituye y mantiene el orden alfabético', async () => {
    await clientes.cargar();
    clientes.actualizar(empresa(3, 'Agencia Brisa'));
    clientes.actualizar({ ...empresa(1, 'Clínica Solana'), sector: 'Sanidad' });
    expect(clientes.lista().map((e) => e.nombre)).toEqual(['Agencia Brisa', 'Clínica Solana', 'Hotel Mirador']);
    expect(clientes.lista().find((e) => e.id === 1)?.sector).toBe('Sanidad');
  });
});
