# Backend — API de Umbral

API REST de Umbral: autenticación propia (JWT + refresh tokens rotados), cuatro roles,
aislamiento multiempresa, ciclo de vida de incidencias, ingesta de eventos de los sensores y
auditoría.

**Stack:** Python 3.12 · FastAPI · SQLAlchemy 2 async (asyncpg) · Alembic · Pydantic ·
PyJWT · argon2-cffi · slowapi · uvicorn · gestionado con [uv](https://docs.astral.sh/uv/).

Todos los comandos de este documento se ejecutan **desde `backend/`**.

---

## Estructura

```
backend/
├── app/
│   ├── main.py            Aplicación, middlewares (prefijo /api, cabeceras) y manejador de errores
│   ├── config.py          Configuración por variables de entorno (pydantic-settings)
│   ├── routers/           HTTP y validación de entrada. Sin lógica de negocio
│   ├── servicios/         Reglas de negocio, permisos y auditoría, en un único sitio
│   ├── repositorios.py    Acceso a datos (SQLAlchemy). Sin reglas
│   ├── modelos.py         Tablas
│   ├── esquemas.py        Esquemas de entrada y salida (Pydantic), siempre separados
│   ├── seguridad.py       Argon2id, emisión y verificación de JWT, refresh tokens
│   ├── dependencias.py    Usuario actual y roles requeridos
│   ├── limitador.py       Rate limit (slowapi)
│   ├── tiempo_real.py     Difusión de eventos por SSE
│   ├── demo.py            Datos de demostración
│   └── cli.py             crear-admin, sembrar-demo
├── alembic/versions/      Migraciones 0001 → 0007
├── tests/                 Tests de integración (pytest)
├── Dockerfile             Imagen multi-stage, sin uv en la final, uid 10001
└── pyproject.toml         Dependencias y configuración de ruff, bandit, pytest y coverage
```

La regla de capas es estricta: **un router nunca decide permisos y un repositorio nunca aplica
reglas**. Todo lo que es «quién puede hacer qué» vive en `servicios/`.

---

## Arranque

### Con Docker (desde la raíz del repo)

```bash
docker compose up -d --build
docker compose exec api python -m app.cli crear-admin admin@example.com
```

### Sin Docker

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Hace falta un PostgreSQL accesible y un `backend/.env` con `DATABASE_URL` (driver
`postgresql+asyncpg`) y `JWT_SECRETO`. La configuración se lee de `.env` en el directorio desde el
que se arranca.

### CLI

| Comando | Qué hace |
|---|---|
| `python -m app.cli crear-admin <email>` | Crea el primer admin, o restablece uno existente (revoca sus sesiones). Pide la contraseña sin eco |
| `python -m app.cli sembrar-demo` | Clientes, cuentas e incidencias ficticias. Idempotente. Ejecutar **antes** de que envíen los sensores |

---

## Tests y calidad

```bash
uv run pytest --cov                                  # integración, SQLite en memoria
TEST_DATABASE_URL=postgresql+asyncpg://usuario:clave@localhost:5432/bd_test \
  uv run pytest --cov                                # contra PostgreSQL real, como en la CI

uv run ruff check . && uv run ruff format --check .  # lint (incluye reglas de seguridad S) y formato
uv run bandit -c pyproject.toml -r app               # SAST
uv run pip-audit --strict                            # dependencias vulnerables
```

- **Integración, no unitarias aisladas**: cada test levanta la app real en memoria y le habla por
  HTTP con `httpx`. Se comprueba lo que vería un cliente: códigos, cuerpos y efectos en la BD.
- **Cobertura mínima del 80 %** (`fail_under` en `pyproject.toml`); la actual ronda el 96 %.
- **`tests/test_migraciones.py`** compara las migraciones con los modelos: cambiar un modelo sin
  generar su migración rompe la CI. También comprueba que el downgrade deja la BD vacía.
- **`tests/e2e_semilla.py`** no es un test: siembra la BD desechable de los E2E del frontend y se
  niega a correr con `ENTORNO=produccion` (sus cuentas tienen una contraseña publicada en el repo).

| Fichero | Qué cubre |
|---|---|
| `test_auth.py` | Login, mismo error exista o no el email, rate limit, tokens manipulados, caducados y `alg=none`, rotación y reutilización del refresh, logout |
| `test_auth_web.py` | Cookie de refresco endurecida, rotación, reutilización, logout, `Path` tras el proxy |
| `test_registro.py` | Registro público, cuenta pendiente, unión con código de invitación |
| `test_gestor.py` | Alcance del gestor sobre su empresa; segunda barrera de aislamiento |
| `test_empresas.py` | CRUD de clientes y aislamiento entre empresas (defensa en profundidad) |
| `test_incidentes.py` | Permisos por rol, IDOR, máquina de estados, notas internas, borrado lógico |
| `test_usuarios.py` | Altas, filtros, contraseñas, revocación inmediata, activar y desactivar |
| `test_eventos.py` | Token de ingesta, limpieza de datos de internet, filtros, triaje, SSE |
| `test_plataforma.py` | Salud, cabeceras de seguridad, CORS, prefijo `/api` |
| `test_migraciones.py` | Migraciones frente a modelos |
| `test_demo.py` | Semilla de demostración idempotente |

### Nueva migración

```bash
uv run alembic revision --autogenerate -m "descripcion del cambio"
```

---

## Variables de entorno

| Variable | Obligatoria | Por defecto | Descripción |
|---|---|---|---|
| `JWT_SECRETO` | Siempre | De desarrollo, solo en local | **Secreta.** Clave de firma HS256. Mínimo 32 caracteres: la API no arranca con menos. Quien la tenga puede fabricar tokens de cualquier usuario |
| `DATABASE_URL` | Sin Docker | URL local de desarrollo | `postgresql+asyncpg://…`. Con Docker la construye el compose |
| `POSTGRES_USER` / `POSTGRES_DB` | No | `incidentes` | Usuario y base de datos (compose) |
| `POSTGRES_PASSWORD` | En producción | De desarrollo, solo en local | Contraseña de Postgres (compose) |
| `ENTORNO` | No | `produccion` en la imagen | `desarrollo`, `produccion` o `test`. En producción no existen `/docs` ni `/openapi.json` |
| `CORS_ORIGENES` | No | vacío | Orígenes permitidos, separados por comas. Nunca `*`. El front propio va en el mismo origen y no lo necesita |
| `API_PREFIJO` | No | vacío (`/api` en el compose) | Prefijo con el que el proxy publica la API. La API lo quita ella misma |
| `INGESTA_TOKEN` | Para el panel | vacío (ingesta desactivada) | Token de servicio compartido con los sensores. Mínimo 32 caracteres. **No** es un JWT de usuario |
| `COOKIE_REFRESCO_RUTA` | No | `/auth/web` (`/api/auth/web` en el compose) | `Path` de la cookie de refresco tal como la ve el navegador |
| `MFA_CLAVE` | Siempre | De desarrollo, solo en local | **Secreta.** Cifra los secretos TOTP (AES-GCM). Mínimo 32 caracteres, distinta de `JWT_SECRETO`. Si se pierde, ningún MFA vuelve a validar |
| `MFA_OBLIGATORIO_PERSONAL` | No | `false` | MFA opcional. Con `true`, admin y analista no ven nada hasta activarlo |
| `URL_PUBLICA` | Para OAuth | vacío (sin Google ni GitHub) | URL de la web, sin barra final. Con ella se construye el `redirect_uri` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | No | vacío | Activan el login con Google. El secreto es **secreto** |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | No | vacío | Activan el login con GitHub. El secreto es **secreto** |
| `COOKIE_OAUTH_RUTA` | No | `/auth/oauth` (`/api/auth/oauth` en el compose) | `Path` de la cookie del flujo OAuth |
| `ACCESO_MINUTOS` | No | `15` | Vida del token de acceso |
| `REFRESCO_DIAS` | No | `7` | Vida del token de refresco |
| `FORWARDED_ALLOW_IPS` | No | `*` en el compose | IPs de las que uvicorn acepta `X-Forwarded-For` |
| `API_PUERTO` | No | `8000` | Puerto local de la API (solo `docker-compose.override.yml`) |
| `BACKUP_INTERVALO_SEGUNDOS` | No | `86400` | Cada cuánto se hace un `pg_dump` |
| `BACKUP_RETENCION_DIAS` | No | `7` | Días que se conservan los volcados |

Genera los secretos con `openssl rand -hex 32`. Usa hexadecimal: la contraseña de Postgres va
dentro de `DATABASE_URL`, y caracteres como `@`, `:` o `/` la romperían.

---

## Endpoints

Con `ENTORNO=desarrollo`, la referencia interactiva está en `/docs`.

| Método | Ruta | Quién |
|---|---|---|
| `GET` | `/salud` | Público |
| `POST` | `/auth/registro` | Público, 5/min. Crea un `usuario` **sin empresa** (pendiente). Responde igual exista o no el email |
| `POST` | `/auth/login`, `/auth/refrescar`, `/auth/logout` | Público. Para clientes que no son navegador: el refresco viaja en el cuerpo |
| `POST` | `/auth/web/login`, `/auth/web/refrescar`, `/auth/web/logout` | Público. Para el navegador: el refresco va en cookie `HttpOnly` |
| `GET` | `/usuarios/yo` | Autenticado. Incluye `empresa_nombre` (solo el nombre, nunca el código de invitación) |
| `PATCH` | `/usuarios/yo/contrasena` | Autenticado, 5/min. Pide la actual y revoca todas las sesiones |
| `POST` | `/usuarios/yo/empresa` | Cuenta pendiente, 5/min: se une a su empresa con el código de invitación |
| `GET`, `POST` | `/usuarios` | admin |
| `PATCH` | `/usuarios/{id}/rol`, `/activo`, `/contrasena` | admin (nunca sobre sí mismo) |
| `GET`, `POST` | `/empresas` · `GET`, `PATCH` `/empresas/{id}` | admin |
| `POST` | `/empresas/{id}/codigo` | admin: regenera el código de invitación de un cliente |
| `GET` | `/mi-empresa`, `/mi-empresa/usuarios`, `/mi-empresa/sensores` | gestor |
| `POST` | `/mi-empresa/codigo` | gestor: regenera su código (el anterior deja de valer) |
| `PATCH` | `/mi-empresa/usuarios/{id}/activo`, `/contrasena` | gestor: solo los `usuario` de su empresa; el resto, 404 |
| `GET`, `POST` | `/incidentes` | Autenticado (el listado se filtra por rol y empresa) |
| `GET`, `PATCH`, `DELETE` | `/incidentes/{id}` | Según rol y propiedad (borrado lógico, solo admin) |
| `PATCH` | `/incidentes/{id}/estado`, `/notas` | analista asignado o admin |
| `PATCH` | `/incidentes/{id}/asignar` | admin |
| `POST` | `/eventos` | Sensores (cabecera `X-Ingesta-Token`, no JWT) |
| `GET` | `/eventos`, `/eventos/resumen`, `/eventos/sensores`, `/eventos/stream` | admin (SSE en `/stream`) |
| `PATCH` | `/eventos/{id}` | admin: triaje |
| `POST` | `/eventos/{id}/incidente` | admin: abre una incidencia desde un evento |
| `GET` | `/eventos/por-incidente/{id}` | admin |
| `GET` | `/auditoria` | admin |

Un recurso que no te pertenece devuelve **404**, no 403, para no confirmar que existe. Los
listados admiten `limite` (máximo 100) y `desplazamiento`.

---

## Despliegue y operación

- La imagen aplica las migraciones al arrancar (`alembic upgrade head`) y sirve con uvicorn sin
  cabecera `Server`.
- Un único worker: el rate limit vive en memoria. Escalar a varias réplicas exige pasarlo a Redis.
- La IP real (rate limit y auditoría) llega por `X-Forwarded-For` de Traefik. Uvicorn solo confía
  en esa cabecera porque la API no publica ningún puerto.

### Backups

El servicio `backup` del compose hace un `pg_dump` (formato custom) cada 24 horas al volumen
`backups`, con permisos `600`, y borra los de más de 7 días. Un volcado fallido no deja un
fichero a medias: el log muestra `backup FALLIDO`.

```bash
docker compose logs backup                     # "backup ok: /backups/incidentes_<fecha>.dump"
docker compose exec backup ls -l /backups      # volcados disponibles
docker compose exec backup sh -c 'pg_restore --clean --if-exists -d "$PGDATABASE" /backups/<fichero>.dump'
```

El volumen vive en la misma máquina: protege de borrados y corrupción, no de perder el servidor.
Para una copia externa, configura en Dokploy un *Volume Backup* del volumen `backups` hacia S3.
