import { APIRequestContext } from '@playwright/test';

import { entrar, expect, menu, test } from './ayudas';
import { CUENTAS, INGESTA_TOKEN } from './datos.mjs';

/** Lo que haría un sensor desplegado en un cliente: enviar un lote a la API. */
async function enviarEvento(request: APIRequestContext, evento: Record<string, unknown>) {
  const r = await request.post('/api/eventos', {
    headers: { 'X-Ingesta-Token': INGESTA_TOKEN },
    data: {
      eventos: [{ tipo: 'otro', severidad: 'baja', metodo: 'GET', servicio: 'senuelo', ...evento }],
    },
  });
  expect(r.status()).toBe(202);
}

test.describe('Centro de seguridad', () => {
  test('un evento de un sensor aparece en vivo en el Panel, con su cliente', async ({ page, request }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page.getByText('En vivo', { exact: true })).toBeVisible();

    await enviarEvento(request, {
      origen_ip: '203.0.113.77',
      tipo: 'fichero_sensible',
      severidad: 'critica',
      ruta: '/.env',
      empresa: 'clinica-solana',
    });
    const feed = page.locator('.ip', { hasText: '203.0.113.77' });
    await expect(feed).toBeVisible();
    await expect(page.getByText('Clínica Solana').first()).toBeVisible();
  });

  test('la ingesta rechaza un token incorrecto', async ({ request }) => {
    const r = await request.post('/api/eventos', {
      headers: { 'X-Ingesta-Token': 'token-inventado-que-no-es-el-bueno-1234567' },
      data: { eventos: [{ origen_ip: '203.0.113.1', tipo: 'otro', severidad: 'baja', metodo: 'GET', ruta: '/' }] },
    });
    expect(r.status()).toBe(401);
  });

  test('una ruta con HTML malicioso se muestra como texto, sin ejecutarse (XSS almacenado)', async ({ page, request }) => {
    const carga = '/buscar?q=<img src=x onerror=alert(1)>';
    await enviarEvento(request, { origen_ip: '198.51.100.66', ruta: carga, empresa: 'transportes-ibarra' });

    await entrar(page, CUENTAS.admin);
    await menu(page, 'Eventos');
    // Se ve literal; el fixture `vigilancia` fallaría si saltara un alert o una violación de CSP
    await expect(page.getByText(carga).first()).toBeVisible();
    await expect(page.locator('img[src="x"]')).toHaveCount(0);
  });

  test('la pantalla de Sensores muestra el señuelo de cada cliente enviando', async ({ page, request }) => {
    await enviarEvento(request, { origen_ip: '192.0.2.10', ruta: '/wp-login.php', empresa: 'clinica-solana' });

    await entrar(page, CUENTAS.admin);
    await menu(page, 'Sensores');
    const fila = page.getByRole('row', { name: /Clínica Solana/ });
    await expect(fila.first()).toContainText('Señuelo');
    await expect(fila.first()).toContainText('Enviando');
  });
});
