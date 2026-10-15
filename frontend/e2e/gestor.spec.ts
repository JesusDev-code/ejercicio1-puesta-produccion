import { entrar, expect, intentarEntrar, menu, salir, test, tokenDe, unico } from './ayudas';
import { CUENTAS, PUERTOS } from './datos.mjs';

test.describe('Gestor de una empresa cliente', () => {
  test('ve las incidencias de toda su empresa, con quién las reportó, y no las de otra', async ({ page, request }) => {
    // Una de su trabajadora y otra de otro cliente, creadas por la API
    const crear = async (email: string, titulo: string) => {
      const token = await tokenDe(request, email);
      const r = await request.post(`http://127.0.0.1:${PUERTOS.web}/api/incidentes`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { titulo, descripcion: 'Creada para el E2E del gestor.', severidad: 'baja', categoria: 'otro' },
      });
      expect(r.ok()).toBe(true);
    };
    const propia = unico('Impresora con credenciales por defecto');
    const ajena = unico('Incidencia de otro cliente');
    await crear(CUENTAS.ibarra, propia);
    await crear(CUENTAS.solana, ajena);

    await entrar(page, CUENTAS.gestoraIbarra);
    await expect(page).toHaveURL(/\/incidentes$/);
    const fila = page.getByRole('row', { name: new RegExp(propia) });
    await expect(fila).toBeVisible();
    await expect(fila).toContainText(CUENTAS.ibarra); // columna «Reportada por»
    await expect(page.getByText(ajena)).toHaveCount(0);
    // Ni centro de seguridad ni administración del MSSP
    await expect(page.getByRole('link', { name: 'Panel' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Clientes' })).toHaveCount(0);
  });

  test('regenera el código de invitación: el nuevo sustituye al anterior', async ({ page }) => {
    await entrar(page, CUENTAS.gestoraIbarra);
    await menu(page, 'Equipo e invitaciones');
    const codigo = page.getByLabel('Código de invitación');
    await expect(codigo).toHaveValue(/^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$/);
    const antes = await codigo.inputValue();

    await page.getByRole('button', { name: 'Regenerar' }).click();
    await page.getByRole('button', { name: 'Sí, regenerar' }).click();
    await expect(page.getByRole('status')).toContainText('Código regenerado');
    await expect(codigo).not.toHaveValue(antes);
  });

  test('desactiva a una trabajadora de su empresa, que ya no puede entrar, y la reactiva', async ({ page }) => {
    await entrar(page, CUENTAS.gestoraIbarra);
    await menu(page, 'Equipo e invitaciones');
    const fila = page.getByRole('row', { name: new RegExp(CUENTAS.ibarra) });
    await fila.getByRole('button', { name: 'Desactivar' }).click();
    await expect(page.getByRole('status')).toContainText('ya no puede entrar');
    await salir(page);

    await intentarEntrar(page, CUENTAS.ibarra);
    await expect(page.getByRole('alert')).toContainText('Email o contraseña incorrectos');

    await entrar(page, CUENTAS.gestoraIbarra);
    await menu(page, 'Equipo e invitaciones');
    await page.getByRole('row', { name: new RegExp(CUENTAS.ibarra) }).getByRole('button', { name: 'Reactivar' }).click();
    await expect(page.getByRole('status')).toContainText('puede volver a entrar');
  });
});
