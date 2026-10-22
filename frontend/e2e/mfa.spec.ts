import { entrar, expect, intentarEntrar, salir, test, tokenDe, totp } from './ayudas';
import { CONTRASENA, CUENTAS, PUERTOS } from './datos.mjs';

const API = `http://127.0.0.1:${PUERTOS.web}/api`;

test.describe('Verificación en dos pasos', () => {
  test('se activa en Mi cuenta y desde entonces el login pide el código', async ({ page, request }) => {
    // Cuenta propia de esta prueba: activar MFA en una compartida rompería las demás
    const cab = { Authorization: `Bearer ${await tokenDe(request, CUENTAS.admin)}` };
    const empresa = (await (await request.get(`${API}/empresas?limite=1`, { headers: cab })).json()).elementos[0];
    const email = `mfa-${Date.now().toString(36)}@ibarra.example.com`;
    const alta = await request.post(`${API}/usuarios`, {
      headers: cab,
      data: { email, contrasena: CONTRASENA, rol: 'usuario', empresa_id: empresa.id },
    });
    expect(alta.status()).toBe(201);

    await entrar(page, email);
    await page.goto('/cuenta');
    await page.getByLabel('Confirma tu contraseña').fill(CONTRASENA);
    await page.getByRole('button', { name: 'Activar verificación' }).click();

    // El QR se dibuja como SVG: ni imágenes data: ni HTML inyectado (CSP y Trusted Types)
    await expect(page.getByRole('img', { name: /Código QR/ })).toBeVisible();
    const secreto = (await page.locator('.secreto').textContent()) ?? '';
    await page.getByLabel('Código de la app').fill(totp(secreto));
    await page.getByRole('button', { name: 'Activar', exact: true }).click();

    const codigos = page.getByRole('list', { name: 'Códigos de recuperación' }).getByRole('listitem');
    await expect(codigos).toHaveCount(10);
    const recuperacion = (await codigos.first().textContent())!.trim();
    await page.getByRole('button', { name: 'Ya los he guardado' }).click();
    await expect(page.getByRole('heading', { name: 'Activada' })).toBeVisible();

    // Login en dos pasos con la app. El código de la activación ya está gastado (anti-replay):
    // se usa el del paso siguiente, que la API acepta por la tolerancia de ±30 s
    await salir(page);
    await intentarEntrar(page, email);
    await expect(page.getByRole('heading', { name: 'Verificación en dos pasos' })).toBeVisible();
    await page.getByLabel('Código de tu app de autenticación').fill(totp(secreto, 30));
    await page.getByRole('button', { name: /Verificar/ }).click();
    await page.waitForURL(/\/incidentes$/);

    // Y con un código de recuperación, que solo vale una vez
    await salir(page);
    for (const esperado of ['ok', 'gastado']) {
      await intentarEntrar(page, email);
      await page.getByLabel('Código de tu app de autenticación').fill(recuperacion);
      await page.getByRole('button', { name: /Verificar/ }).click();
      if (esperado === 'ok') {
        await page.waitForURL(/\/incidentes$/);
        await salir(page);
      } else {
        await expect(page.getByRole('alert')).toContainText('Código incorrecto');
      }
    }
  });
});
