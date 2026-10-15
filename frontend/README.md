# Frontend — consola web de Umbral

SPA en **Angular 21** (componentes *standalone*, señales y `OnPush`) con la web pública de
Kaelum Security y la consola de Umbral. En producción la sirve un nginx sin privilegios con una
CSP estricta.

Todos los comandos de este documento se ejecutan **desde `frontend/`**.

---

## Arranque

```bash
npm ci
npm start            # http://localhost:4200
```

`npm start` reenvía `/api/*` a la API en `127.0.0.1:8000` (`proxy.conf.json`), igual que Traefik
en producción. Levanta antes la API (`docker compose up -d` desde la raíz).

| Script | Qué hace |
|---|---|
| `npm start` | Servidor de desarrollo con proxy a la API |
| `npm run build` | Build de producción en `dist/web/browser` |
| `npm test` | Tests unitarios (Vitest) |
| `npm run e2e` | Tests E2E (Playwright) |

---

## Estructura

```
frontend/
├── src/app/
│   ├── core/          Lógica sin interfaz: sesión, interceptor HTTP, guardas de ruta, cliente de
│   │                  la API, modelos, stream de eventos (SSE), errores y validadores
│   ├── paginas/       Una pantalla por fichero (login, registro, incidencias, panel, usuarios…)
│   ├── ui/            Componentes reutilizables: shell, gráficos, selector, paginador
│   ├── app.routes.ts  Rutas y guardas
│   └── app.config.ts  Proveedores (router, HTTP con interceptor)
├── e2e/               Tests E2E y el entorno que los levanta (entorno.mjs)
├── nginx/             default.conf y cabeceras-seguridad.conf (CSP, HSTS…)
├── public/            Estáticos
└── Dockerfile         Build con Node + imagen final nginx-unprivileged
```

---

## Decisiones de seguridad

- **Mismo origen.** Front y API bajo el mismo dominio (`/` y `/api`): sin CORS.
- **Token de acceso solo en memoria** (una señal), nunca en `localStorage`. El de refresco va en
  la cookie `__Secure-refresco` (`HttpOnly; Secure; SameSite=Strict`, `Path=/api/auth/web`): el
  JavaScript no puede leerla y otra web no puede hacer que el navegador la envíe. Al recargar, la
  sesión se recupera con un refresco.
- **401 → refresco silencioso → reintento**, con **un único refresco a la vez**: dos en paralelo
  enviarían la misma cookie y la API lo trataría como reutilización (revoca la familia).
- **CSP estricta** sin `'unsafe-inline'`: nonce por respuesta para los estilos de Angular y
  **Trusted Types**. Estilos dinámicos por CSSOM, no con atributos `style`.
- **Fuentes empaquetadas** (`@fontsource`): ningún recurso de terceros, ni Google Fonts.
- La interfaz solo **oculta** acciones según el rol; quien autoriza es siempre la API.

---

## Tests

### Unitarios (Vitest + jsdom)

```bash
npx ng test --watch=false
```

| Fichero | Qué cubre |
|---|---|
| `core/sesion.spec.ts` | Token solo en memoria; dos refrescos simultáneos hacen una sola petición; restaurar sin cookie; salir aunque la API no responda |
| `core/interceptor.spec.ts` | Añade el Bearer; no lo envía a rutas públicas; ante un 401 refresca y repite una vez; si el refresco falla, cierra la sesión |
| `core/guardas.spec.ts` | Sesión obligatoria, solo invitados, solo admin, landing solo sin sesión |
| `core/clientes.spec.ts` | Caché de clientes, nombres y opciones de filtro y alta |
| `core/errores.spec.ts` | Mensajes por código sin trazas; campos señalados por un 422 |
| `paginas/clientes.spec.ts` | El código sugerido para un cliente siempre lo acepta la API |

### End-to-end (Playwright)

```bash
npx playwright install chromium   # solo la primera vez
npx playwright test
```

No necesita Docker ni toca nada real. `e2e/entorno.mjs` (lanzado por Playwright):

1. Compila el front **para producción**.
2. Crea una BD SQLite desechable, aplica las migraciones y siembra cuentas
   (`../backend/tests/e2e_semilla.py`). Necesita `uv` instalado.
3. Arranca la **API real** desde `../backend`.
4. Sirve el build con **las mismas cabeceras que nginx** (leídas de
   `nginx/cabeceras-seguridad.conf`) y reenvía `/api` a la API, como Traefik.

Cada prueba **falla si hay una violación de CSP o de Trusted Types, un error de JavaScript o un
diálogo inesperado** (fixture `vigilancia` en `e2e/ayudas.ts`).

| Fichero | Escenarios |
|---|---|
| `acceso.spec.ts` | Mensaje de error idéntico (sin enumeración), almacenamiento vacío y cookie blindada, recarga que mantiene la sesión, logout, cookie robada y reutilizada |
| `registro.spec.ts` | Registro, cuenta pendiente y unión con código; email duplicado sin filtrar nada |
| `gestor.spec.ts` | Ve las incidencias de su empresa y no las de otra; regenera el código de invitación; desactiva y reactiva a una trabajadora suya |
| `incidencias.spec.ts` | Reportar; otro cliente no la ve ni por id (404) |
| `administracion.spec.ts` | Alta de cliente y usuario; baja del cliente que le cierra la puerta; auditoría |
| `sensores.spec.ts` | Evento en vivo por SSE, token de ingesta incorrecto, XSS almacenado mostrado como texto |

Si algo falla, cada servicio deja su log en `test-results/<servicio>.log` y Playwright guarda
traza y captura.
