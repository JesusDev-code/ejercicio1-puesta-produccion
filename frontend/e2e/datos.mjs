// Datos compartidos por el entorno E2E (entorno.mjs) y las pruebas (*.spec.ts).
// Las cuentas las crea tests/e2e_semilla.py en una BD desechable: no son reales.

export const PUERTOS = { web: 4321, api: 8765 };

export const JWT_SECRETO = 'secreto-jwt-solo-para-e2e-con-mas-de-32-caracteres';
export const INGESTA_TOKEN = 'token-e2e-de-ingesta-con-mas-de-32-caracteres';

export const CONTRASENA = 'contrasena-e2e-segura'; // la misma que en tests/e2e_semilla.py

export const CUENTAS = {
  admin: 'admin@kaelum.example.com',
  ibarra: 'ana@ibarra.example.com',
  gestoraIbarra: 'marta@ibarra.example.com',
  solana: 'luis@solana.example.com',
};
