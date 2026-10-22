import { entrar, expect, intentarEntrar, salir, test } from './ayudas';
import { CUENTAS, PUERTOS } from './datos.mjs';

test.describe('Acceso', () => {
  test('la web pública se ve sin sesión y lleva al login', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Vigilamos tu red');
    await page.getByRole('link', { name: /Acceso clientes/ }).first().click();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('la política de privacidad es pública y está enlazada desde la web', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Privacidad' }).click();
    await expect(page).toHaveURL(/\/privacidad$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Política de privacidad');
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

  test('el admin entra al Panel: el token de acceso no se guarda y el refresco es una cookie blindada', async ({
    page,
    context,
  }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Panel');

    const almacenado = await page.evaluate(() => ({
      local: localStorage.length,
      sesion: sessionStorage.length,
      cookiesVisibles: document.cookie,
    }));
    expect(almacenado.local).toBe(0);
    expect(almacenado.sesion).toBe(0);
    // HttpOnly: ni el código de la app ni un XSS pueden leer el token de refresco
    expect(almacenado.cookiesVisibles).toBe('');

    const cookies = await context.cookies();
    expect(cookies).toHaveLength(1);
    expect(cookies[0]).toMatchObject({
      name: '__Secure-refresco',
      path: '/api/auth/web', // el navegador solo la manda a login, refrescar y logout
      httpOnly: true,
      secure: true,
      sameSite: 'Strict', // una web ajena no puede provocar que se envíe (CSRF)
    });
  });

  test('recargar la página mantiene la sesión (refresco con la cookie)', async ({ page }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await page.reload();
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Panel');
  });

  test('cerrar sesión revoca el refresco: recargar ya no recupera nada', async ({ page, context }) => {
    await entrar(page, CUENTAS.admin);
    await expect(page).toHaveURL(/\/monitorizacion$/);
    await salir(page);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Vigilamos tu red');
    expect(await context.cookies()).toEqual([]);

    await page.goto('/monitorizacion');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('una cookie de refresco robada y reutilizada tumba la sesión entera', async ({ page, context, request }) => {
    await entrar(page, CUENTAS.admin);
    const [robada] = await context.cookies();

    // El atacante usa su copia primero: la API rota el token y la copia del navegador queda vieja
    const uso = await request.post(`http://127.0.0.1:${PUERTOS.web}/api/auth/web/refrescar`, {
      headers: { Cookie: `${robada.name}=${robada.value}` },
    });
    expect(uso.ok()).toBe(true);

    // El navegador legítimo refresca con el token ya rotado: reutilización → familia revocada
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
  });
});
