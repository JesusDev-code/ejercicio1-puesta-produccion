import { Page } from '@playwright/test';

import { entrar, expect, menu, salir, test, tokenDe, unico } from './ayudas';
import { CUENTAS } from './datos.mjs';

async function reportar(page: Page, titulo: string): Promise<string> {
  await menu(page, 'Reportar incidencia');
  await page.getByLabel('Título').fill(titulo);
  await page.locator('label.sev', { hasText: 'Media' }).click();
  await page.locator('#n-cat').click();
  await page.getByRole('option', { name: 'Phishing' }).click();
  await page.getByLabel('Descripción').fill('Correo que pide las credenciales del portal del empleado.');
  await page.getByRole('button', { name: /Enviar reporte/ }).click();
  await expect(page).toHaveURL(/\/incidentes\/\d+$/);
  return page.url().split('/').pop()!;
}

test.describe('Incidencias y aislamiento entre clientes', () => {
  test('un trabajador de un cliente reporta una incidencia y la ve en su lista', async ({ page }) => {
    await entrar(page, CUENTAS.ibarra);
    await expect(page).toHaveURL(/\/incidentes$/);
    // Un trabajador no ve el centro de seguridad ni la administración
    await expect(page.getByRole('link', { name: 'Panel' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Clientes' })).toHaveCount(0);

    const titulo = unico('Correo sospechoso');
    await reportar(page, titulo);
    await expect(page.getByText(titulo).first()).toBeVisible();

    await menu(page, 'Incidencias');
    await expect(page.getByRole('link', { name: new RegExp(titulo) })).toBeVisible();
  });

  test('otro cliente no la ve en su lista, y la API se la niega aunque conozca el id', async ({ page, request }) => {
    await entrar(page, CUENTAS.ibarra);
    const titulo = unico('Portátil lento');
    const id = await reportar(page, titulo);
    await salir(page);

    await entrar(page, CUENTAS.solana);
    await expect(page).toHaveURL(/\/incidentes$/);
    await expect(page.getByText(titulo)).toHaveCount(0);

    // IDOR contra la API, con un token válido de otra empresa: 404, como si no existiera
    const deSolana = { Authorization: `Bearer ${await tokenDe(request, CUENTAS.solana)}` };
    expect((await request.get(`/api/incidentes/${id}`, { headers: deSolana })).status()).toBe(404);
    const editar = await request.patch(`/api/incidentes/${id}`, { headers: deSolana, data: { titulo: 'Mío' } });
    expect(editar.status()).toBe(404);
    // Control: su dueña sí la ve
    const deIbarra = { Authorization: `Bearer ${await tokenDe(request, CUENTAS.ibarra)}` };
    expect((await request.get(`/api/incidentes/${id}`, { headers: deIbarra })).status()).toBe(200);
  });

  test('el admin la ve, con el cliente al que pertenece', async ({ page }) => {
    await entrar(page, CUENTAS.ibarra);
    const titulo = unico('USB en recepción');
    const id = await reportar(page, titulo);
    await salir(page);

    await entrar(page, CUENTAS.admin);
    await menu(page, 'Incidencias');
    await page.getByRole('link', { name: new RegExp(titulo) }).click();
    await expect(page).toHaveURL(new RegExp(`/incidentes/${id}$`));
    await expect(page.getByText(titulo).first()).toBeVisible();
    await expect(page.getByText('Transportes Ibarra')).toBeVisible();
  });
});
