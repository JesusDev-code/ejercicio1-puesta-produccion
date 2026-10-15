// Datos compartidos por el entorno E2E (entorno.mjs) y las pruebas (*.spec.ts).
// Las cuentas las crea tests/e2e_semilla.py en el EMULADOR de Firebase: no son reales.

// Ojo: 4400 y 4500 los usa por defecto el emulador de Firebase (hub y logging)
export const PUERTOS = { web: 4321, api: 8765, auth: 9099, hub: 4410, logging: 4510 };

export const PROYECTO_FIREBASE = 'demo-umbral'; // «demo-»: el emulador no necesita cuenta de Google
export const API_KEY = 'clave-e2e';
export const INGESTA_TOKEN = 'token-e2e-de-ingesta-con-mas-de-32-caracteres';

export const CONTRASENA = 'contrasena-e2e-segura'; // la misma que en tests/e2e_semilla.py

export const CUENTAS = {
  admin: 'admin@kaelum.example.com',
  ibarra: 'ana@ibarra.example.com',
  solana: 'luis@solana.example.com',
};
