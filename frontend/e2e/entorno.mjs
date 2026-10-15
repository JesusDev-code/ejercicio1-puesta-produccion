// Entorno E2E completo, sin Docker y sin tocar nada real:
//
//   1. Compila el front para producción.
//   2. Crea una BD SQLite nueva, aplica las migraciones y siembra clientes y cuentas.
//   3. Arranca la API real con su autenticación propia (JWT + cookie de refresco).
//   4. Sirve el build con las MISMAS cabeceras que nginx (leídas de nginx/cabeceras-seguridad.conf,
//      CSP y Trusted Types incluidas) y reenvía /api a la API, como hace Traefik.
//
// Lo lanza Playwright (webServer). Al terminar, mata todos los procesos hijos.

import { execSync, spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { createReadStream, createWriteStream, existsSync, mkdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { createServer, request } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { INGESTA_TOKEN, JWT_SECRETO, PUERTOS } from './datos.mjs';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const BACKEND = resolve(WEB, '..', 'backend');
const DIST = join(WEB, 'dist', 'web', 'browser');
const DIR_BD = join(tmpdir(), 'umbral-e2e');
const WINDOWS = process.platform === 'win32';

const entornoApi = {
  ...process.env,
  ENTORNO: 'desarrollo',
  DATABASE_URL: `sqlite+aiosqlite:///${join(DIR_BD, 'e2e.db').replaceAll('\\', '/')}`,
  JWT_SECRETO,
  // El navegador ve la API bajo /api, igual que en producción detrás de Traefik
  COOKIE_REFRESCO_RUTA: '/api/auth/web',
  // Todas las pruebas entran desde 127.0.0.1: con 5 logins/min darían 429 al azar. El límite
  // lo prueba tests/test_auth.py::test_rate_limit_en_login, que es su sitio
  LIMITADOR_ACTIVO: 'false',
  INGESTA_TOKEN,
  API_PREFIJO: '/api',
  PYTHONUTF8: '1',
};

// --- Procesos hijos ---

const hijos = [];

/** Cada servicio deja su salida en test-results/<nombre>.log: ahí se mira cuando algo falla. */
function lanzar(nombre, comando, args, opciones) {
  mkdirSync(join(WEB, 'test-results'), { recursive: true });
  const log = createWriteStream(join(WEB, 'test-results', `${nombre}.log`));
  const hijo = spawn(comando, args, { stdio: ['ignore', 'pipe', 'pipe'], shell: WINDOWS, detached: !WINDOWS, ...opciones });
  hijo.stdout.pipe(log);
  hijo.stderr.pipe(log);
  hijo.on('exit', (codigo) => {
    if (!cerrando) {
      console.error(`[e2e] ${nombre} terminó (código ${codigo})`);
      cerrar(1);
    }
  });
  hijos.push(hijo);
  return hijo;
}

let cerrando = false;
function cerrar(codigo = 0) {
  if (cerrando) return;
  cerrando = true;
  for (const hijo of hijos) {
    try {
      // En Windows, matar el árbol entero: npx y uv lanzan procesos que si no quedarían huérfanos
      if (WINDOWS) execSync(`taskkill /pid ${hijo.pid} /T /F`, { stdio: 'ignore' });
      else process.kill(-hijo.pid, 'SIGTERM');
    } catch {
      // ya había terminado
    }
  }
  process.exit(codigo);
}
for (const senal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(senal, () => cerrar(0));

async function esperar(url, nombre, segundos = 120) {
  const limite = Date.now() + segundos * 1000;
  while (Date.now() < limite) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {
      // aún no escucha
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  console.error(`[e2e] ${nombre} no respondió en ${segundos} s`);
  cerrar(1);
}

// --- Servidor del front: las mismas cabeceras que nginx ---

const conf = readFileSync(join(WEB, 'nginx', 'cabeceras-seguridad.conf'), 'utf8');
const CABECERAS = [...conf.matchAll(/^add_header\s+(\S+)\s+"([^"]+)"/gm)].map((m) => [m[1], m[2]]);
if (!CABECERAS.some(([k]) => k === 'Content-Security-Policy')) {
  throw new Error('No se encontró la CSP en nginx/cabeceras-seguridad.conf');
}

function cabeceras(nonce) {
  // Exactamente la CSP de producción: el front solo habla con su propio origen
  return Object.fromEntries(CABECERAS.map(([clave, valor]) => [clave, valor.replaceAll('$nonce', nonce)]));
}

const TIPOS = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.json': 'application/json',
  '.txt': 'text/plain; charset=utf-8',
  '.ico': 'image/x-icon',
};

function servirFront() {
  const index = readFileSync(join(DIST, 'index.html'), 'utf8');
  const servidor = createServer((req, res) => {
    const ruta = new URL(req.url ?? '/', 'http://localhost').pathname;

    // /api -> API (como Traefik). Se reenvía en flujo: el SSE del panel funciona igual
    if (ruta.startsWith('/api/') || ruta === '/api') {
      const salida = request(
        { host: '127.0.0.1', port: PUERTOS.api, path: req.url, method: req.method, headers: req.headers },
        (respuesta) => {
          res.writeHead(respuesta.statusCode ?? 502, respuesta.headers);
          respuesta.pipe(res);
        },
      );
      salida.on('error', () => {
        res.writeHead(502);
        res.end();
      });
      req.pipe(salida);
      return;
    }

    const nonce = randomBytes(16).toString('hex');
    const fichero = normalize(join(DIST, decodeURIComponent(ruta)));
    if (!fichero.startsWith(DIST)) {
      res.writeHead(403);
      res.end();
      return;
    }
    if (ruta !== '/' && ruta !== '/index.html' && existsSync(fichero) && statSync(fichero).isFile()) {
      res.writeHead(200, { ...cabeceras(nonce), 'Content-Type': TIPOS[extname(fichero)] ?? 'application/octet-stream' });
      createReadStream(fichero).pipe(res);
      return;
    }
    // Rutas de la SPA: index.html con el nonce de esta respuesta (como el sub_filter de nginx)
    res.writeHead(200, { ...cabeceras(nonce), 'Content-Type': TIPOS['.html'], 'Cache-Control': 'no-store' });
    res.end(index.replaceAll('CSP_NONCE', nonce));
  });
  servidor.on('error', (e) => {
    console.error(`[e2e] el front no puede escuchar en ${PUERTOS.web}: ${e.message}`);
    cerrar(1);
  });
  servidor.listen(PUERTOS.web, '127.0.0.1', () => console.log(`[e2e] front en http://127.0.0.1:${PUERTOS.web}`));
}

// --- Arranque ---

rmSync(DIR_BD, { recursive: true, force: true });
mkdirSync(DIR_BD, { recursive: true });

if (!process.env.E2E_SIN_BUILD) {
  execSync('npx ng build', { cwd: WEB, stdio: 'inherit' });
}

execSync('uv run alembic upgrade head', { cwd: BACKEND, env: entornoApi, stdio: 'inherit' });
execSync('uv run python -m tests.e2e_semilla', { cwd: BACKEND, env: entornoApi, stdio: 'inherit' });

// --no-server-header como en el Dockerfile: el entorno de pruebas reproduce producción
lanzar('api', 'uv', ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PUERTOS.api), '--no-server-header'], {
  cwd: BACKEND,
  env: entornoApi,
});
await esperar(`http://127.0.0.1:${PUERTOS.api}/salud`, 'La API');

servirFront();
