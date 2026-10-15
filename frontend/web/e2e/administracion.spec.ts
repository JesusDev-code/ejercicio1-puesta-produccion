import { entrar, expect, intentarEntrar, menu, salir, test, unico } from './ayudas';
import { CUENTAS } from './datos.mjs';

test.describe('Administración de clientes y usuarios', () => {
  test('alta de un cliente y de un usuario suyo, que entra; al dar de baja el cliente, ya no', async ({ page }) => {
    const cliente = unico('Hotel Mirador');
    const email = `recepcion-${Date.now()}@mirador.example.com`;

    // 1. Alta del cliente (el código se sugiere a partir del nombre)
    await entrar(page, CUENTAS.admin);
    await menu(page, 'Clientes');
    await page.getByRole('button', { name: /Nuevo cliente/ }).click();
    await page.getByLabel('Nombre').fill(cliente);
    await page.getByLabel('Sector').fill('Hostelería');
    await expect(page.getByLabel('Código')).toHaveValue(/^hotel-mirador-/);
    await page.getByRole('button', { name: 'Crear cliente' }).click();
    await expect(page.getByRole('status').filter({ hasText: `Cliente ${cliente} creado` })).toBeVisible();

    // 2. Alta de un usuario de ese cliente, con contraseña generada
    await menu(page, 'Usuarios');
    await page.getByRole('button', { name: /Nuevo usuario/ }).click();
    await page.locator('#a-email').fill(email);
    await page.locator('#a-empresa').click();
    await page.getByRole('option', { name: cliente }).click();
    await page.getByRole('button', { name: 'Generar' }).click();
    const contrasena = await page.locator('#a-pass').inputValue();
    expect(contrasena.length).toBeGreaterThanOrEqual(12);
    await page.getByRole('button', { name: 'Crear cuenta' }).click();
    await expect(page.getByRole('status').filter({ hasText: `Cuenta ${email} creada` })).toBeVisible();
    await salir(page);

    // 3. El usuario nuevo entra (su cuenta existe en Firebase) y aterriza en sus incidencias
    await entrar(page, email, contrasena);
    await expect(page).toHaveURL(/\/incidentes$/);
    await salir(page);

    // 4. El admin da de baja el cliente
    await entrar(page, CUENTAS.admin);
    await menu(page, 'Clientes');
    const fila = page.getByRole('row', { name: new RegExp(cliente) });
    await fila.getByRole('button', { name: 'Dar de baja' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'dado de baja' })).toBeVisible();
    await salir(page);

    // 5. Firebase le deja iniciar sesión (no sabe de clientes), pero Umbral le cierra la puerta
    await intentarEntrar(page, email, contrasena);
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('la auditoría registra las entradas al sistema', async ({ page }) => {
    await entrar(page, CUENTAS.admin);
    await menu(page, 'Auditoría');
    await expect(page.getByText(CUENTAS.admin).first()).toBeVisible();
  });
});
