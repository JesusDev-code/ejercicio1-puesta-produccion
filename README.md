# Umbral — gestión de incidentes de ciberseguridad

[![CI](https://github.com/JesusDev-code/ejercicio1-puesta-produccion/actions/workflows/ci.yml/badge.svg)](https://github.com/JesusDev-code/ejercicio1-puesta-produccion/actions/workflows/ci.yml)

**Umbral** es la plataforma de *Kaelum Security*, un proveedor ficticio de ciberseguridad
gestionada (MSSP). Reúne en una sola aplicación:

- **Gestión de incidencias**: los trabajadores de cada cliente reportan sospechas y un analista
  las lleva hasta el cierre.
- **Centro de seguridad**: sensores señuelo detectan sondeos reales de internet y el panel los
  muestra en vivo para hacer el triaje.
- **Administración multicliente**: clientes, cuentas y auditoría, con aislamiento estricto entre
  empresas.

Cuatro roles (`usuario`, `gestor`, `analista`, `admin`), registro público con código de
invitación por empresa y auditoría de todas las acciones sensibles.

> Proyecto académico del módulo *Puesta en producción segura* (Curso de Especialización en
> Ciberseguridad). Ninguna empresa, cliente ni servicio es real.

| | |
|---|---|
| **Backend** | Python 3.12 · FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL 17 · uv |
| **Frontend** | Angular 21 (standalone, señales) · TypeScript 5.9 · nginx sin privilegios |
| **Sensores** | Python 3.12, solo librería estándar |
| **Infraestructura** | Docker Compose · Dokploy + Traefik (TLS Let's Encrypt) · GitHub Actions |

---

## Índice

1. [Estructura del repositorio](#estructura-del-repositorio)
2. [Arquitectura](#arquitectura)
3. [Arranque rápido con Docker](#arranque-rápido-con-docker)
4. [Desarrollo local](#desarrollo-local)
5. [Testing](#testing)
6. [Calidad y seguridad del código](#calidad-y-seguridad-del-código)
7. [CI/CD](#cicd)
8. [Despliegue](#despliegue)
9. [Documentación](#documentación)

---

## Estructura del repositorio

Monorepo con un directorio por servicio. Cada uno se construye, se prueba y se despliega por
separado, y tiene su propio README.

```
.
├── backend/                 API REST (FastAPI)                       → backend/README.md
│   ├── app/                 Código: routers → servicios → repositorios
│   ├── alembic/             Migraciones de la base de datos
│   ├── tests/               Tests de integración (pytest)
│   ├── Dockerfile           Imagen multi-stage sin root
│   └── pyproject.toml       Dependencias y configuración de ruff, bandit, pytest y coverage
├── frontend/                SPA Angular                              → frontend/README.md
│   ├── src/app/             core/ (sesión, API, guardas) · paginas/ · ui/
│   ├── e2e/                 Tests E2E (Playwright) y su entorno
│   ├── nginx/               Configuración de nginx y cabeceras de seguridad (CSP)
│   └── Dockerfile           Build de Angular + nginx sin privilegios
├── senuelo/                 Señuelo (honeypot de registro) y generador de demo → senuelo/README.md
├── postman/                 Colección de la API y entornos           → postman/README.md
├── scripts/                 Utilidades de operación (cuentas de evaluación)
├── docs/
│   └── UMBRAL.md            Documentación funcional y de seguridad completa
├── .github/workflows/ci.yml Integración y despliegue continuos
├── docker-compose.yml       Producción (Dokploy)
└── docker-compose.override.yml  Solo local: secretos de desarrollo y puerto de la API
```

---

## Arquitectura

```
                         Internet
                            │
                      ┌─────┴──────┐  Traefik (Dokploy): TLS con Let's Encrypt
                      │   proxy    │
                      └─┬───┬────┬─┘
            dominio /   │   │/api│            dominio del señuelo
                        ▼   ▼    │                    ▼
                   ┌─────┐ ┌─────┴──┐           ┌───────────┐
    navegador ───► │ web │ │  api   │ ◄──────── │ senuelo   │  eventos reales
                   └─────┘ └──┬─────┘ ◄──────── │ generador │  eventos de demo
                 frontend/    │  backend/       └───────────┘
                              ▼
                         ┌─────────┐   ┌────────┐
                         │   db    │◄──│ backup │  pg_dump diario
                         └─────────┘   └────────┘
```

| Servicio (compose) | Código | Papel | Expuesto |
|---|---|---|---|
| `web` | `frontend/` | nginx sirviendo el Angular compilado con CSP estricta | Sí, `/` |
| `api` | `backend/` | Lógica, permisos, autenticación y auditoría | Sí, `/api` del mismo dominio |
| `db` | — | PostgreSQL 17 | No |
| `senuelo` | `senuelo/` | Honeypot de registro: clasifica sondeos y los envía a la API | Sí, dominio propio |
| `generador` | `senuelo/` | Telemetría de demostración para el panel | No |
| `backup` | — | `pg_dump` periódico con retención | No |

Front y API comparten dominio: **sin CORS** para la aplicación propia. El detalle de cada pieza
está en [`docs/UMBRAL.md`](docs/UMBRAL.md#3-arquitectura).

---

## Arranque rápido con Docker

Requisito: Docker con el plugin Compose. No hace falta Python, Node ni configuración previa.

```bash
docker compose up -d --build
docker compose exec api python -m app.cli crear-admin admin@example.com   # pide la contraseña
docker compose exec api python -m app.cli sembrar-demo                    # opcional: datos de demo
```

- La API queda en `http://127.0.0.1:8000` (documentación interactiva en `/docs`).
- Las migraciones se aplican solas al arrancar el contenedor `api`.
- La base de datos **no publica puerto**: solo la alcanza la API.
- En local, `docker-compose.override.yml` aporta secretos de **desarrollo** (públicos, sin valor
  fuera de tu máquina). Para usar los tuyos, copia `.env.example` a `.env`: sus valores mandan.

Para la interfaz web en local, arranca el frontend con `npm start` (ver
[Desarrollo local](#desarrollo-local)): reenvía `/api` a la API igual que Traefik en producción.

---

## Desarrollo local

| Componente | Requisitos | Arranque | Detalle |
|---|---|---|---|
| Backend | Python 3.12, [uv](https://docs.astral.sh/uv/), PostgreSQL | `cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload` | [`backend/README.md`](backend/README.md) |
| Frontend | Node 22 | `cd frontend && npm ci && npm start` → `http://localhost:4200` | [`frontend/README.md`](frontend/README.md) |
| Sensores | Python 3.12 | `cd senuelo && MODO=generador API_URL=… INGESTA_TOKEN=… python arranque.py` | [`senuelo/README.md`](senuelo/README.md) |

Lo más cómodo: base de datos y API con `docker compose up -d`, y el frontend con `npm start`.

---

## Testing

Cinco niveles, de lo más aislado a lo más completo. Todos corren en la CI en cada push.

| Nivel | Herramienta | Dónde | Qué prueba | Nº |
|---|---|---|---|---|
| Unitarias de los sensores | pytest | `senuelo/test_clasificador.py` | Cada regla del clasificador tipo WAF, con casos que deben y que no deben coincidir | 12 |
| Integración de la API | pytest + httpx | `backend/tests/` | Cada endpoint por HTTP contra la app real y una BD real: permisos por rol, IDOR, aislamiento entre clientes, tokens manipulados, rotación y reutilización del refresh, revocación inmediata, migraciones | 183 |
| Unitarias del frontend | Vitest + jsdom | `frontend/src/**/*.spec.ts` | Sesión (token solo en memoria, un único refresco a la vez), interceptor, guardas, errores | 53 |
| End-to-end | Playwright | `frontend/e2e/` | Navegador real → front compilado para producción con la CSP de nginx → API real → BD desechable | 22 |
| Contrato de la API | Postman / Newman | `postman/` | Los cuatro roles, registro e invitaciones, IDOR, `alg=none`, refresh tokens, rate limit | 126 peticiones · 191 aserciones |

```bash
# Backend: integración (SQLite en memoria por defecto) con cobertura mínima del 80 %
cd backend && uv run pytest --cov

# Igual, pero contra PostgreSQL real, como en la CI
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://usuario:clave@localhost:5432/bd_test uv run pytest --cov

# Sensores (se ejecutan con el entorno del backend: no tienen dependencias propias)
cd backend && uv run pytest ../senuelo

# Frontend: unitarias y E2E (el E2E levanta solo API, BD y front; no necesita Docker)
cd frontend && npx ng test --watch=false
cd frontend && npx playwright test
```

Puntos clave del diseño de las pruebas:

- **La API se prueba por HTTP, no por funciones sueltas.** Un permiso bien escrito pero mal
  enganchado a su router no protege nada, y solo un test por HTTP lo detecta.
- **Los E2E verifican la política de seguridad de producción.** Cada prueba falla si el
  navegador registra una violación de la CSP o de Trusted Types, un error de JavaScript o un
  diálogo inesperado.
- **Las migraciones se prueban contra los modelos** (`test_migraciones.py`): si un modelo cambia
  sin su migración, la CI falla.

Fichero a fichero, qué cubre cada test: [`docs/UMBRAL.md` §15](docs/UMBRAL.md#15-pruebas-unitarias-integración-e2e-y-ci).

---

## Calidad y seguridad del código

| Herramienta | Tipo | Ámbito |
|---|---|---|
| ruff | Lint (incluidas las reglas de seguridad `S` de bandit) y formato | backend y senuelo |
| bandit | Análisis estático de seguridad (SAST) | `backend/app` |
| pip-audit `--strict` | Vulnerabilidades en dependencias (SCA) | backend |
| npm audit | Vulnerabilidades en dependencias de runtime, nivel alto | frontend |
| Lockfiles | Builds reproducibles | `backend/uv.lock`, `frontend/package-lock.json` |

```bash
cd backend
uv run ruff check . ../senuelo && uv run ruff format --check . ../senuelo
uv run bandit -c pyproject.toml -r app
uv run pip-audit --strict
```

Cómo se mitiga cada categoría del OWASP Top 10:2025:
[`docs/UMBRAL.md` §13](docs/UMBRAL.md#13-owasp-top-10).

---

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) se ejecuta en cada push y pull request.

```
calidad-y-tests ──┬──► imagen ─────────────┐
                  ├──► senuelo ────────────┤
frontend ─────────┴──► e2e ────────────────┴──► deploy   (solo push a main)
```

| Job | Qué hace |
|---|---|
| `calidad-y-tests` | ruff → bandit → pip-audit → pytest contra PostgreSQL 17 de servicio → lint y tests de los sensores |
| `imagen` | Build de la imagen de la API y comprobación de que no corre como root |
| `frontend` | npm audit → Vitest → build de producción → imagen nginx sin root |
| `senuelo` | Build de la imagen de los sensores sin root |
| `e2e` | Suite de Playwright completa. Si falla, sube informe, trazas y logs de cada servicio |
| `deploy` | Solo en push a `main` y si **todo** lo anterior pasa: despliega el compose vía API de Dokploy |

El auto-deploy de Dokploy está **desactivado**: el único camino a producción es pasar la CI. Si
no, los controles serían un aviso, no una barrera. El job `deploy` usa los secrets
`DOKPLOY_URL`, `DOKPLOY_API_KEY` y `DOKPLOY_COMPOSE_ID` del environment `production` de GitHub.

---

## Despliegue

`docker-compose.yml` es el de producción y lo despliega Dokploy. Resumen de lo que lo hace
seguro:

- Contenedores sin root, sistema de ficheros de solo lectura, `cap_drop: ALL` y
  `no-new-privileges`.
- La API y la base de datos no publican puertos: solo les llega tráfico de Traefik y de la red
  interna del compose.
- Los secretos viven en Dokploy, nunca en el repositorio. Sin ellos no arranca nada: Postgres
  rechaza una contraseña vacía y la API un `JWT_SECRETO` de menos de 32 caracteres.
- `pg_dump` diario con 7 días de retención (servicio `backup`).

Dominios, variables, puesta en marcha desde cero y restauración de copias:
[`docs/UMBRAL.md` §14](docs/UMBRAL.md#14-despliegue) y [`backend/README.md`](backend/README.md).

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/UMBRAL.md`](docs/UMBRAL.md) | Documentación completa: funcionalidad, roles, multiempresa, autenticación, seguridad capa a capa, OWASP, pruebas y decisiones de diseño |
| [`backend/README.md`](backend/README.md) | API: arranque, variables de entorno, endpoints, migraciones, CLI, backups |
| [`frontend/README.md`](frontend/README.md) | SPA: arranque, estructura, decisiones de seguridad, tests unitarios y E2E |
| [`senuelo/README.md`](senuelo/README.md) | Señuelo y generador de eventos |
| [`postman/README.md`](postman/README.md) | Colección de la API: qué recorre y cómo ejecutarla |
