import { APIRequestContext, Page, expect, test as base } from '@playwright/test';

import { API_KEY, CONTRASENA, PUERTOS } from './datos.mjs';

/**
 * Todas las pruebas usan este `test`: falla si el navegador registra una violación de la CSP o
 * de Trusted Types, o un error de JavaScript sin capturar. Así cada flujo comprueba también que
 * la política de seguridad de producción no rompe nada (ni deja pasar nada).
 */
export const test = base.extend<{ vigilancia: string[] }>({
  vigilancia: [
    async ({ page }, usar) => {
      const problemas: string[] = [];
      page.on('console', (m) => {
        const texto = m.text();
        if (/Content Security Policy|Trusted Type|TrustedHTML|TrustedScript/i.test(texto)) problemas.push(texto);
      });
      page.on('pageerror', (e) => problemas.push(`Error JS: ${e.message}`));
      page.on('dialog', async (d) => {
        problemas.push(`Diálogo inesperado (¿XSS?): ${d.message()}`);
        await d.dismiss();
      });
      await usar(problemas);
      expect(problemas, 'violaciones de CSP, errores JS o diálogos').toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** Rellena el login y pulsa Entrar, sin esperar resultado (para los casos que deben fallar). */
export async function intentarEntrar(page: Page, email: string, contrasena = CONTRASENA): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Contraseña').fill(contrasena);
  await page.getByRole('button', { name: /Entrar/ }).click();
}

/** Login correcto: espera a aterrizar (Panel o Incidencias) antes de seguir, sin carreras. */
export async function entrar(page: Page, email: string, contrasena = CONTRASENA): Promise<void> {
  await intentarEntrar(page, email, contrasena);
  await page.waitForURL(/\/(monitorizacion|incidentes)$/);
}

export async function salir(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page).toHaveURL(/\/$/);
}

/** Enlace del menú lateral (hay otros enlaces con el mismo texto, p. ej. «Usuarios» de un cliente). */
export async function menu(page: Page, nombre: string): Promise<void> {
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: nombre, exact: true }).click();
}

/**
 * ID token de una cuenta, pedido al emulador igual que lo hace el SDK en el navegador. Sirve para
 * atacar la API directamente: la seguridad la impone la API, no la interfaz.
 */
export async function tokenDe(request: APIRequestContext, email: string): Promise<string> {
  const r = await request.post(
    `http://127.0.0.1:${PUERTOS.auth}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${API_KEY}`,
    { data: { email, password: CONTRASENA, returnSecureToken: true } },
  );
  expect(r.ok()).toBe(true);
  return (await r.json()).idToken;
}

/** Texto único por ejecución, para no chocar con datos de otras pruebas. */
export function unico(prefijo: string): string {
  return `${prefijo} ${Date.now().toString(36)}`;
}
