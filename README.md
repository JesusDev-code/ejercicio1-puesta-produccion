# API de incidentes de ciberseguridad

> **Documentación completa del proyecto** (qué hace, tecnologías, seguridad, OWASP, pruebas):
> [`docs/UMBRAL.md`](docs/UMBRAL.md).

API REST para registrar y gestionar incidentes de ciberseguridad, con tres roles (`usuario`,
`analista`, `admin`), ciclo de vida de los incidentes y auditoría de todas las acciones
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

No hay registro público. El primer admin se crea por consola, con la contraseña pedida sin eco;
el resto de cuentas las da de alta ese admin desde la web (Usuarios → Nuevo usuario):

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
y las variables `FIREBASE_*` de un proyecto de Firebase con Email/Password activado.

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
| `FIREBASE_CREDENCIALES` | En producción | vacío | **Secreta.** JSON de la cuenta de servicio de Firebase (Admin SDK), en base64. Solo la recibe la API |
| `FIREBASE_API_KEY` / `FIREBASE_AUTH_DOMAIN` / `FIREBASE_PROJECT_ID` | En producción (salvo `AUTH_DOMAIN`) | vacío | Config web de Firebase. **No** son secretas: la API se las da al front en `GET /config/cliente` |
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
| `FORWARDED_ALLOW_IPS` | No | `*` en el compose | IPs de las que uvicorn acepta `X-Forwarded-For`. Ver «Despliegue» |

---

## Endpoints

| Método | Ruta | Quién |
|---|---|---|
| `GET` | `/config/cliente` | Público. Config web de Firebase para el front (sin secretos) |
| `POST` | `/auth/sesion`, `/auth/salida` | Autenticado. El login lo hace el navegador contra Firebase; estas rutas solo lo registran en la auditoría. **No hay registro público**: las cuentas las crea un admin |
| `GET` | `/usuarios/yo` | Autenticado |
| `PATCH` | `/usuarios/yo/contrasena` | Autenticado (pide la actual; revoca todas las sesiones) |
| `GET` | `/usuarios` | admin (filtros `rol` y `email`) |
| `POST` | `/usuarios` | admin: alta de cuenta con email, contraseña inicial y rol |
| `PATCH` | `/usuarios/{id}/contrasena` | admin: restablece la contraseña y cierra sus sesiones (no sobre sí mismo) |
| `PATCH` | `/usuarios/{id}/rol` | admin (no sobre sí mismo) |
| `PATCH` | `/usuarios/{id}/activo` | admin (no sobre sí mismo) |
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
- **Firebase Authentication con persistencia en memoria** (`inMemoryPersistence`): el ID token
  no se guarda en `localStorage`, `sessionStorage` ni IndexedDB (lo que Firebase hace por
  defecto). Un XSS no encuentra nada persistente. Coste asumido: recargar pide entrar otra vez.
- **La API verifica el ID token** con el Admin SDK (`check_revoked=True`) y decide rol, empresa y
  si la cuenta está activa con su propia base de datos. Un `uid` que no está en la BD no entra,
  aunque alguien se registre por su cuenta en Firebase con la API key pública.
- **401 → token nuevo de Firebase → reintento** una vez; si vuelve a fallar, al login.
- **Contrapartida:** los intentos fallidos los ve y frena Firebase, no nuestra auditoría.
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

En `postman/` están la colección y los entornos `local` y `produccion`. Recorre los tres roles con
casos positivos y negativos, incluidos ataques al token (`alg=none`, firma manipulada), IDOR,
mass assignment, reutilización de refresh tokens y rate limit.

1. Crea el admin (ver arriba).
2. En el entorno, rellena `admin_email` y `admin_contrasena` como **valor actual**: así no se
   exportan.
3. Ejecuta la colección completa con el Runner, en orden.

Entre dos ejecuciones espera un minuto: la última carpeta agota el rate limit del login a
propósito. Para lanzarla desde la terminal:

```bash
npx newman run postman/api-incidentes.postman_collection.json \
  -e postman/local.postman_environment.json \
  --env-var admin_email=admin@example.com --env-var admin_contrasena=...
```

Usa dominios como `example.com`: el validador de email rechaza los de uso especial, como `.test`.

---

## CI

`.github/workflows/ci.yml` se ejecuta en cada push y en cada pull request:

1. `ruff` (lint y formato) → `bandit` → `pip-audit --strict` → `pytest` contra un PostgreSQL 17
   de servicio.
2. Build de la imagen Docker y comprobación de que no corre como root.

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
  Sin secretos no arranca nada: Postgres rechaza una contraseña vacía y la API, en producción,
  se niega a arrancar sin las credenciales de Firebase.
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
├── identidad.py    Firebase Authentication (verificar tokens, altas, contraseñas)
└── cli.py          crear-admin
alembic/            Migraciones
tests/              pytest
postman/            Colección y entornos
```
