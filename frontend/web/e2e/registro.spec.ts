import { APIRequestContext, Page } from '@playwright/test';

import { expect, intentarEntrar, menu, test, tokenDe } from './ayudas';
import { CUENTAS, PUERTOS } from './datos.mjs';

const CONTRASENA_NUEVA = 'frase-larga-de-registro-e2e';

/** El código de invitación vigente de una empresa, leído como lo haría el admin. */
async function codigoDe(request: APIRequestContext, codigoEmpresa: string): Promise<string> {
  const token = await tokenDe(request, CUENTAS.admin);
  const r = await request.get(`http://127.0.0.1:${PUERTOS.web}/api/empresas`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const empresa = (await r.json()).elementos.find((e: { codigo: string }) => e.codigo === codigoEmpresa);
  return empresa.codigo_invitacion;
}

async function registrarse(page: Page, email: string): Promise<void> {
  await page.goto('/login');
  await page.getByRole('link', { name: 'Crear cuenta' }).click();
  await expect(page).toHaveURL(/\/registro$/);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Contraseña', { exact: true }).fill(CONTRASENA_NUEVA);
  await page.getByLabel('Repite la contraseña').fill(CONTRASENA_NUEVA);
  await page.getByRole('button', { name: /Crear cuenta/ }).click();
  await expect(page).toHaveURL(/\/login\?registrado=1$/);
}

test.describe('Registro y unión a una empresa', () => {
  test('alguien nuevo se registra, entra sin empresa y se une con el código', async ({ page, request }) => {
    const email = `nuevo-${Date.now()}@ibarra.example.com`;
    await registrarse(page, email);
    await expect(page.getByRole('status')).toContainText('tu cuenta está creada');

    // Sin empresa, la consola entera le está cerrada: aterriza en «Unirme a mi empresa»
    await intentarEntrar(page, email, CONTRASENA_NUEVA);
    await expect(page).toHaveURL(/\/unirse$/);
    await page.goto('/incidentes');
    await expect(page).toHaveURL(/\/unirse$/);

    // Un código inventado no sirve
    await page.getByLabel('Código').fill('AAAA-BBBB-CCCC');
    await page.getByRole('button', { name: /Unirme/ }).click();
    await expect(page.getByRole('alert')).toContainText('no es válido');

    // El bueno, tecleado de cualquier manera, sí
    const codigo = await codigoDe(request, 'transportes-ibarra');
    await page.getByLabel('Código').fill(codigo.toLowerCase().replaceAll('-', ' '));
    await page.getByRole('button', { name: /Unirme/ }).click();
    await expect(page).toHaveURL(/\/incidentes$/);
    await menu(page, 'Reportar incidencia');
    await expect(page).toHaveURL(/\/incidentes\/nuevo$/);
  });

  test('registrarse con un email que ya existe no revela nada ni le quita la cuenta', async ({ page }) => {
    await registrarse(page, CUENTAS.ibarra);
    // Mismo mensaje que un registro nuevo...
    await expect(page.getByRole('status')).toContainText('tu cuenta está creada');
    // ...pero la contraseña nueva no entra: la cuenta sigue siendo de su dueña
    await intentarEntrar(page, CUENTAS.ibarra, CONTRASENA_NUEVA);
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');
  });

  test('una cuenta pendiente puede cerrar sesión desde «Unirme a mi empresa»', async ({ page }) => {
    const email = `pendiente-${Date.now()}@example.com`;
    await registrarse(page, email);
    await intentarEntrar(page, email, CONTRASENA_NUEVA);
    await expect(page).toHaveURL(/\/unirse$/);
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto('/unirse');
    await expect(page).toHaveURL(/\/login$/);
  });
});
