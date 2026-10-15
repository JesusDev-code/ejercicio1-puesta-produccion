# API de incidentes de ciberseguridad

> **Documentación completa del proyecto** (qué hace, tecnologías, seguridad, OWASP, pruebas):
> [`docs/UMBRAL.md`](docs/UMBRAL.md).

API REST para registrar y gestionar incidentes de ciberseguridad, con cuatro roles (`usuario`,
`gestor`, `analista`, `admin`), registro público con código de invitación por empresa, ciclo de vida de los incidentes y auditoría de todas las acciones
sensibles. Alcance pequeño y acabado profesional: el peso está en la seguridad, los tests y el
despliegue.

Roles, permisos, ciclo de vida, multiempresa, seguridad y pruebas: [`docs/UMBRAL.md`](docs/UMBRAL.md).

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 async + Alembic · PostgreSQL 17 · uv · Docker.

---

## Arranque rápido (Docker)

Requisito: Docker con el plugin Compose (Docker Engine, Docker Desktop o equivalente). No hace
falta nada más: ni Python ni configuración previa.

```bash
docker compose up -d --build
```

- La API queda en `http://127.0.0.1:8000`, con la documentación en `/docs`.
- Las migraciones se aplican solas al arrancar el contenedor.
- La base de datos **no publica puerto**: solo la alcanza la API.
- Si el puerto 8000 está ocupado: `API_PUERTO=8081 docker compose up -d --build`.

En local, `docker-compose.override.yml` aporta secretos de desarrollo para que arranque sin
configurar nada. Son públicos y solo sirven en local. Para usar los tuyos, copia `.env.example`
a `.env` y rellénalo: sus valores mandan sobre los de desarrollo. Si la base de datos ya se creó
con otra contraseña, recréala con `docker compose down -v`.

Genera los secretos con `openssl rand -hex 32`. Usa hexadecimal: la contraseña de Postgres va
dentro de `DATABASE_URL`, y caracteres como `@`, `:` o `/` la romperían.

### Crear el primer admin

El primer admin se crea por consola, con la contraseña pedida sin eco. El resto de cuentas, o
las da de alta un admin desde la web (Usuarios → Nuevo usuario), o se registran solas en
`/registro` y se unen a su empresa con el código de invitación que les da su gestor:

```bash
docker compose exec api python -m app.cli crear-admin admin@example.com
```

---

## Desarrollo sin Docker

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Hace falta un PostgreSQL accesible y un `.env` con `DATABASE_URL` (driver `postgresql+asyncpg`)
y `JWT_SECRETO`.

### Tests y calidad

```bash
uv run pytest --cov                    # SQLite en memoria
TEST_DATABASE_URL=postgresql+asyncpg://usuario:clave@localhost:5432/bd_test \
  uv run pytest --cov                  # contra PostgreSQL real, como en CI

uv run ruff check . && uv run ruff format --check .
uv run bandit -c pyproject.toml -r app
uv run pip-audit --strict
```

La cobertura mínima es del 80 %. `tests/test_migraciones.py` comprueba que las migraciones
coinciden con los modelos: si se cambia un modelo sin generar su migración, el test falla.

### Nueva migración

```bash
uv run alembic revision --autogenerate -m "descripcion del cambio"
```

---

## Variables de entorno

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `JWT_SECRETO` | Siempre | De desarrollo, solo en local | **Secreta.** Clave de firma de los JWT (HS256). Mínimo 32 caracteres: la API no arranca con menos. Quien la tenga puede fabricar tokens de cualquier usuario |
| `DATABASE_URL` | Sin Docker | URL local de desarrollo | `postgresql+asyncpg://…`. Con Docker la construye el compose |
| `POSTGRES_USER` / `POSTGRES_DB` | No | `incidentes` | Usuario y base de datos (compose) |
| `POSTGRES_PASSWORD` | En producción | De desarrollo, solo en local | Contraseña de Postgres (compose) |
| `API_PUERTO` | No | `8000` | Puerto local de la API (solo `docker-compose.override.yml`) |
| `BACKUP_INTERVALO_SEGUNDOS` | No | `86400` | Cada cuánto se hace un `pg_dump` |
| `BACKUP_RETENCION_DIAS` | No | `7` | Días que se conservan los volcados |
| `ENTORNO` | No | `produccion` en la imagen | `desarrollo`, `produccion` o `test`. En producción no existen `/docs` ni `/openapi.json` |
| `CORS_ORIGENES` | No | vacío | Orígenes permitidos, separados por comas. Nunca `*`. El frontend propio va en el mismo origen y no lo necesita |
| `API_PREFIJO` | No | vacío (`/api` en el compose) | Prefijo con el que el proxy publica la API. La API lo quita ella misma: no depende del «strip path» del proxy |
| `INGESTA_TOKEN` | Para el panel | vacío (ingesta desactivada) | Token de servicio que comparten la API, el señuelo y el generador. Mínimo 32 caracteres. **No** es un JWT de usuario |
| `COOKIE_REFRESCO_RUTA` | No | `/auth/web` (`/api/auth/web` en el compose) | `Path` de la cookie de refresco tal como la ve el navegador |
| `ACCESO_MINUTOS` | No | `15` | Vida del token de acceso. El compose no la pasa al contenedor |
| `REFRESCO_DIAS` | No | `7` | Vida del token de refresco. El compose no la pasa al contenedor |
| `FORWARDED_ALLOW_IPS` | No | `*` en el compose | IPs de las que uvicorn acepta `X-Forwarded-For`. Ver «Despliegue» |

---

## Endpoints

| Método | Ruta | Quién |
|---|---|---|
| `POST` | `/auth/registro` | Público, 5/min. Crea un `usuario` **sin empresa** (pendiente). Responde igual exista o no el email |
| `POST` | `/auth/login`, `/auth/refrescar`, `/auth/logout` | Público. Para clientes que no son navegador (Postman, scripts) |
| `POST` | `/auth/web/login`, `/auth/web/refrescar`, `/auth/web/logout` | Público. Para el navegador: el refresco va en cookie `HttpOnly`, nunca en el cuerpo |
| `GET` | `/usuarios/yo` | Autenticado |
| `PATCH` | `/usuarios/yo/contrasena` | Autenticado (pide la actual; revoca todas las sesiones) |
| `GET` | `/usuarios` | admin (filtros `rol` y `email`) |
| `POST` | `/usuarios` | admin: alta de cuenta con email, contraseña inicial y rol |
| `PATCH` | `/usuarios/{id}/contrasena` | admin: restablece la contraseña y cierra sus sesiones (no sobre sí mismo) |
| `PATCH` | `/usuarios/{id}/rol` | admin (no sobre sí mismo) |
| `PATCH` | `/usuarios/{id}/activo` | admin (no sobre sí mismo) |
| `POST` | `/usuarios/yo/empresa` | Cuenta pendiente, 5/min: se une a su empresa con el código de invitación |
| `GET` | `/mi-empresa`, `/mi-empresa/usuarios`, `/mi-empresa/sensores` | gestor: su empresa (con el código), su equipo y sus sensores |
| `POST` | `/mi-empresa/codigo` | gestor: regenera el código (el anterior deja de valer) |
| `PATCH` | `/mi-empresa/usuarios/{id}/activo`, `/contrasena` | gestor: solo a los `usuario` de su empresa; el resto, 404 |
| `POST` | `/empresas/{id}/codigo` | admin: regenera el código de cualquier cliente |
| `POST` / `GET` | `/incidentes` | Autenticado (el listado se filtra por rol) |
| `GET` / `PATCH` | `/incidentes/{id}` | Según rol y propiedad |
| `PATCH` | `/incidentes/{id}/estado` | analista asignado o admin |
| `PATCH` | `/incidentes/{id}/asignar` | admin |
| `PATCH` | `/incidentes/{id}/notas` | analista asignado o admin |
| `DELETE` | `/incidentes/{id}` | admin (borrado lógico) |
| `GET` | `/auditoria` | admin |
| `POST` | `/eventos` | Señuelo/generador (cabecera `X-Ingesta-Token`, no JWT) |
| `GET` | `/eventos`, `/eventos/resumen`, `/eventos/stream` | admin (listado, agregados para gráficos, SSE en vivo) |
| `POST` | `/eventos/{id}/incidente` | admin: abre una incidencia desde un evento |
| `PATCH` | `/eventos/{id}` | admin: triaje del evento (`nuevo` / `revisado` / `ignorado` y nota). Se difunde en vivo |
| `GET` | `/eventos/por-incidente/{id}` | admin: evento del que salió una incidencia |
| `GET` | `/salud` | Público |

Un recurso que no te pertenece devuelve **404**, no 403, para no confirmar que existe.

---

## Frontend

Angular 21 en `frontend/web`.

```bash
cd frontend/web
npm ci
npm start            # http://localhost:4200, con la API en 127.0.0.1:8000
```

`npm start` reenvía `/api/*` a la API (`proxy.conf.json`), igual que Traefik en producción.

Decisiones de seguridad:

- **Mismo origen.** El front y la API se sirven bajo el mismo dominio (`/` y `/api`). Sin CORS.
- **Token de acceso solo en memoria**, nunca en `localStorage`. El de refresco va en una cookie
  `__Secure-refresco` `HttpOnly; Secure; SameSite=Strict` con `Path` acotado a `/api/auth/web`:
  el JavaScript no puede leerla y otra web no puede hacer que el navegador la envíe. Al recargar,
  la sesión se recupera con un refresco.
- **401 → refresco silencioso → reintento.** Un único refresco a la vez: dos en paralelo usarían
  la misma cookie y la API lo trataría como reutilización (revoca la familia).
- **CSP estricta** sin `'unsafe-inline'`: nonce por respuesta para los estilos de Angular y
  Trusted Types. Fuentes servidas desde el propio dominio, sin Google Fonts.
- La interfaz solo **oculta** acciones según el rol; quien autoriza es la API.

### Despliegue en Dokploy

El servicio `web` es nginx sin privilegios **solo para estáticos**: el enrutado lo hace Traefik.
En Dokploy, dos dominios con el **mismo host**:

| Servicio | Host | Path | Strip path | Puerto |
|---|---|---|---|---|
| `api` | `incidentes.ejemplo.com` | `/api` | No hace falta | `8000` |
| `web` | `incidentes.ejemplo.com` | `/` | No | `8080` |

---

## Postman

En `postman/` están la colección (126 peticiones, 191 comprobaciones) y los entornos `local` y
`produccion`. Usa las rutas `/auth/*` (el refresco viaja en el cuerpo) y el token de acceso como
Bearer. Recorre:

- los cuatro roles con casos positivos y negativos, mass assignment e IDOR;
- registro (mismo mensaje con un email existente), cuenta pendiente que no ve nada, unión con
  código (inventado → 422) y lo que el gestor puede y no puede tocar;
- tokens manipulados (firma alterada, `alg=none`, inventados);
- refresh tokens: rotación en cada uso, reutilización de uno ya rotado (revoca la familia y tumba
  al momento el access obtenido con la copia), logout;
- revocación inmediata: tras un cambio o restablecimiento de contraseña, o una baja, el token de
  acceso anterior deja de valer aunque no haya caducado;
- clientes y aislamiento: un trabajador de un cliente no ve ni edita lo de otro, ni forzando el
  filtro, y al dar de baja su cliente queda fuera;
- rate limit del login y del cambio de contraseña (la carpeta va la última).

El login admite 5 intentos por minuto e IP. La colección lleva la cuenta y, cuando haría falta un
sexto, **espera** a que se renueve la ventana: por eso tarda algo más de un minuto.

**En local**, contra una API con el limitador activo y un admin creado con `crear-admin`:

```bash
docker compose up -d                                  # o uvicorn a mano
docker compose exec api python -m app.cli crear-admin admin@example.com
npx newman run postman/api-incidentes.postman_collection.json -e postman/local.postman_environment.json \
  --env-var admin_email=admin@example.com --env-var admin_contrasena=<la que elegiste>
```

La pila del E2E (`frontend/web/e2e/entorno.mjs`) **no** sirve para la colección completa: arranca
la API con el rate limit desactivado, porque los E2E entran muchas veces desde la misma IP.

**Contra producción**: rellena `admin_email` y `admin_contrasena` como **valor actual** (así no se
exportan) y ejecuta en orden con el Runner. Cada ejecución crea usuarios, clientes e incidencias de
prueba reales.

Usa dominios como `example.com`: el validador de email rechaza los de uso especial, como `.test`.

---

## CI

`.github/workflows/ci.yml` se ejecuta en cada push y en cada pull request:

| Job | Qué hace |
|---|---|
| `calidad-y-tests` | `ruff` (lint y formato) → `bandit` (SAST) → `pip-audit --strict` (SCA) → `pytest` contra un PostgreSQL 17 de servicio, y tests del señuelo |
| `imagen` | Build de la imagen de la API y comprobación de que no corre como root |
| `frontend` | `npm audit` de runtime, tests unitarios (Vitest), build y la imagen nginx sin root |
| `senuelo` | Build de la imagen del señuelo sin root |
| `e2e` | Playwright: navegador real → front con la CSP de nginx → API real |
| `deploy` | **Solo en push a `main` y si todo lo anterior pasa.** Despliega el compose con la API de Dokploy |

El auto-deploy de Dokploy está **desactivado**: si estuviera activo, desplegaría en cada push
aunque la CI fallara. El job `deploy` necesita, en el environment `production` de GitHub, los
secrets `DOKPLOY_URL` (el panel), `DOKPLOY_API_KEY` y `DOKPLOY_COMPOSE_ID`.

---

## Despliegue

`docker-compose.yml` es el de producción. `docker-compose.override.yml` solo se aplica en local:
publica la API en `127.0.0.1:8000` y no confía en cabeceras de proxy.

En producción:

- La API no publica puertos. Solo le llega tráfico del proxy inverso (Traefik), así que confía
  en su `X-Forwarded-For` para obtener la IP real. La IP real la necesitan el rate limit y la
  auditoría.
- Las variables de entorno se configuran en la plataforma de despliegue, nunca en el repositorio.
  Se despliega solo `docker-compose.yml` (por ejemplo, `docker compose -f docker-compose.yml up`).
  Sin secretos no arranca nada: Postgres rechaza una contraseña vacía y la API un `JWT_SECRETO`
  de menos de 32 caracteres.
- El contenedor de la API corre sin root, con el sistema de ficheros en solo lectura, sin
  capabilities y con `no-new-privileges`.
- Un único worker de uvicorn: el rate limit vive en memoria. Para escalar a varias réplicas hay
  que pasarlo a Redis.

### Backups

El servicio `backup` del compose hace un `pg_dump` (formato custom) cada 24 horas al volumen
`backups` y borra los de más de 7 días. Los ficheros quedan con permisos `600`. Si un volcado
falla, no se guarda un fichero a medias: el log del servicio muestra `backup FALLIDO`.

```bash
docker compose logs backup                     # "backup ok: /backups/incidentes_<fecha>.dump"
docker compose exec backup ls -l /backups      # volcados disponibles
```

Para restaurar un volcado (sustituye el contenido actual de la base de datos):

```bash
docker compose exec backup sh -c 'pg_restore --clean --if-exists -d "$PGDATABASE" /backups/<fichero>.dump'
```

El volumen vive en la misma máquina: protege de borrados accidentales y de corrupción, no de
perder el servidor. Para tener una copia fuera, configura en Dokploy un *Volume Backup* del
volumen `backups` hacia un destino S3, o copia los volcados periódicamente a otra máquina.

### Seguridad del contenedor y de la red

| Medida | Dónde |
|---|---|
| Imagen slim multi-stage, sin uv ni herramientas de build | `Dockerfile` |
| Usuario sin privilegios (uid 10001), código propiedad de root | `Dockerfile` |
| Sistema de ficheros de solo lectura, `/tmp` en memoria | `docker-compose.yml` |
| `cap_drop: ALL` y `no-new-privileges` | `docker-compose.yml` |
| Postgres sin puerto publicado, datos en volumen con nombre | `docker-compose.yml` |
| Sin cabecera `Server` | `Dockerfile` (`--no-server-header`) |

---

## Estructura

```
app/
├── routers/        HTTP y validación. Sin lógica
├── servicios/      Reglas de negocio, permisos y auditoría
├── repositorios.py Acceso a datos
├── modelos.py      Modelos SQLAlchemy
├── esquemas.py     Esquemas Pydantic de entrada y salida
├── seguridad.py    argon2, emisión y verificación de JWT, refresh tokens
└── cli.py          crear-admin
alembic/            Migraciones
tests/              pytest
postman/            Colección y entornos
```
