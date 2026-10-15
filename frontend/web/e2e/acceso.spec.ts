import { entrar, expect, intentarEntrar, salir, test } from './ayudas';
import { API_KEY, CONTRASENA, CUENTAS, PUERTOS } from './datos.mjs';

test.describe('Acceso', () => {
  test('la web pública se ve sin sesión y lleva al login', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Vigilamos tu red');
    await page.getByRole('link', { name: /Acceso clientes/ }).first().click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('una contraseña incorrecta da un mensaje genérico', async ({ page }) => {
    await intentarEntrar(page, CUENTAS.admin, 'no-es-la-contrasena');
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('un email inexistente da el mismo mensaje (sin enumeración)', async ({ page }) => {
    await intentarEntrar(page, 'nadie@kaelum.example.com');
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');
  });

  test('el admin entra al Panel y el token no queda guardado en ningún sitio', async ({ page, context }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Panel');

    const almacenado = await page.evaluate(async () => ({
      local: localStorage.length,
      sesion: sessionStorage.length,
      bases: (await indexedDB.databases()).map((b) => b.name),
    }));
    expect(almacenado.local).toBe(0);
    expect(almacenado.sesion).toBe(0);
    expect(almacenado.bases).not.toContain('firebaseLocalStorageDb');
    expect(await context.cookies()).toEqual([]);
  });

  test('recargar la página pide entrar otra vez (sesión solo en memoria)', async ({ page }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('cerrar sesión vuelve a la web pública', async ({ page }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await salir(page);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Vigilamos tu red');
  });

  test('una cuenta creada por libre en Firebase no entra en Umbral', async ({ page, request }) => {
    // La API key es pública: cualquiera podría registrarse en Firebase. Sin fila en nuestra BD, no entra
    const email = `intruso-${Date.now()}@kaelum.example.com`;
    const alta = await request.post(
      `http://127.0.0.1:${PUERTOS.auth}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=${API_KEY}`,
      { data: { email, password: CONTRASENA, returnSecureToken: true } },
    );
    expect(alta.ok()).toBe(true);

    await intentarEntrar(page, email);
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');
    await expect(page).toHaveURL(/\/login$/);
  });
});
