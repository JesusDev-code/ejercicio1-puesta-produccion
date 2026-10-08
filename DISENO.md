# Diseño — API de gestión de incidentes de ciberseguridad

> Módulo: Puesta en producción segura · Ejercicio 1 · Inicio: 2026-10-08
> Estado: **diseño cerrado**, listo para implementar. Construido con IA bajo directrices del alumno.

## 1. Qué es

Backend REST con FastAPI para registrar y gestionar incidentes de ciberseguridad. Lo consumen
clientes web y móvil (multiplataforma). Alcance pequeño, acabado profesional: el peso está en
la seguridad, los tests y el despliegue, no en la cantidad de funcionalidades.

## 2. Stack

| Pieza | Elección |
|---|---|
| Lenguaje | Python 3.12 |
| Dependencias | uv (`pyproject.toml` + `uv.lock`) |
| Framework | FastAPI |
| ORM / migraciones | SQLAlchemy 2.0 async (asyncpg) + Alembic |
| Base de datos | PostgreSQL |
| Hash de contraseñas | argon2 |
| JWT | access token (~15 min) + refresh token con rotación |
| Rate limiting | slowapi |
| Tests | pytest + httpx (AsyncClient) |
| Calidad / seguridad | ruff, bandit, pip-audit |
| CI | GitHub Actions |
| Despliegue | Dokploy (Traefik + Let's Encrypt), servicio Docker Compose |
| Pruebas manuales | Colección Postman |

**Idioma:** API y código en **español** (rutas, campos, enums, clases y funciones), sin tildes
ni `ñ` en los identificadores.

## 3. Arquitectura

Capas `routers → services → repositories`:

- **routers:** HTTP, validación con Pydantic, dependencias de autenticación. Sin lógica.
- **services:** reglas de negocio, permisos por rol y propiedad, transiciones de estado, auditoría.
- **repositories:** acceso a datos con SQLAlchemy. Sin reglas de negocio.

Los permisos se comprueban en **services**, en un solo sitio, nunca repartidos por los routers.

## 4. Roles y permisos

| Acción | usuario | analista | admin |
|---|---|---|---|
| Registrarse / login | ✅ | ✅ | ✅ |
| Crear incidente | ✅ | ✅ | ✅ |
| Ver incidentes | solo los suyos | solo los asignados | todos |
| Editar título/descripción/categoría | los suyos, solo en `abierto` | ❌ | ✅ |
| Ver y escribir notas internas | ❌ | los asignados | ✅ |
| Cambiar estado | ❌ | los asignados | ✅ |
| Asignar analista | ❌ | ❌ | ✅ |
| Reabrir (`cerrado → abierto`) | ❌ | ❌ | ✅ |
| Borrar (lógico) | ❌ | ❌ | ✅ |
| Cambiar roles / ver auditoría | ❌ | ❌ | ✅ |

- **Registro abierto**: siempre crea el rol `usuario`. El campo `rol` del body se ignora.
- **Primer admin**: comando CLI `python -m app.cli crear-admin`, con la contraseña pedida por consola.
- Acceder a un recurso que no te pertenece devuelve **404**, no 403, para no confirmar que existe.

## 5. Ciclo de vida del incidente

```
abierto ──► en_analisis ──► resuelto ──► cerrado
   ▲                                       │
   └──────────── (solo admin) ─────────────┘
```

- Las transiciones no listadas se rechazan con **409 Conflict**.
- `en_analisis` exige que haya un analista asignado.
- Cada transición queda en la auditoría.

## 6. Modelo de datos

**Usuario:** `id`, `email` (único), `hash_contrasena`, `rol` (`usuario`|`analista`|`admin`),
`activo`, `creado_en`

**Incidente:** `id`, `titulo` (3-120), `descripcion` (≤ 5000, texto plano), `severidad`
(`baja`|`media`|`alta`|`critica`), `categoria` (`phishing`|`malware`|`acceso_no_autorizado`|
`fuga_datos`|`denegacion_servicio`|`otro`), `estado`, `reportante_id`, `analista_id`,
`notas_internas`, `creado_en`, `actualizado_en`, `borrado_en`

**TokenRefresco:** `id`, `usuario_id`, `hash_token`, `familia_id`, `expira_en`, `revocado_en`

**RegistroAuditoria:** `id`, `usuario_id`, `accion`, `recurso`, `recurso_id`, `ip`, `detalle`, `fecha`

- Los incidentes con `borrado_en` no aparecen en ninguna consulta, salvo en la auditoría.
- Los refresh tokens se guardan **hasheados**, nunca en claro.

## 7. Seguridad

- **Contraseñas:** argon2, mínimo 12 caracteres.
- **Refresh tokens:** rotación en cada uso. Si se reutiliza uno ya revocado, se revoca toda su
  familia (señal de robo).
- **Rate limiting:** `/auth/login` y `/auth/registro`, 5 peticiones por minuto y por IP.
- **Auditoría:** login con éxito y fallido, registro, cambios de estado, asignaciones, edición
  de notas, borrados y cambios de rol.
- **Cabeceras:** `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Content-Security-Policy` restrictiva.
- **CORS:** lista blanca de orígenes por variable de entorno, nunca `*`.
- **Esquemas Pydantic** separados de entrada y salida, y salida distinta según el rol:
  `notas_internas` nunca llega al reportante.
- **IDOR:** comprobación de propiedad o asignación en cada acceso.
- **Paginación:** `limite` (máx. 100) y `desplazamiento`. Filtros por estado, severidad y categoría.
- **Secretos** en `.env` (gitignoreado). Existe un `.env.example` sin valores reales.
- **Contenedor** con usuario no-root e imagen slim multi-stage.
- **`/docs` y `/openapi.json`** deshabilitados en producción (`ENTORNO=produccion`).
- **Errores:** sin trazas internas en las respuestas en producción.

## 8. Endpoints

```
POST   /auth/registro
POST   /auth/login
POST   /auth/refrescar
POST   /auth/logout

GET    /usuarios/yo
GET    /usuarios                       (admin)
PATCH  /usuarios/{id}/rol              (admin)

POST   /incidentes
GET    /incidentes                     (filtrado por rol + paginación)
GET    /incidentes/{id}
PATCH  /incidentes/{id}                (reportante en 'abierto' o admin)
PATCH  /incidentes/{id}/estado         (analista asignado o admin)
PATCH  /incidentes/{id}/asignar        (admin)
PATCH  /incidentes/{id}/notas          (analista asignado o admin)
DELETE /incidentes/{id}                (admin, borrado lógico)

GET    /auditoria                      (admin, paginado)
GET    /salud
```

## 9. Tests imprescindibles

**Autenticación**
- Sin token → 401 · token caducado o manipulado → 401
- Refresh rotado: el viejo deja de valer · reutilizar uno revocado revoca la familia
- Logout revoca el refresh
- Superar el rate limit → 429

**Autorización**
- Usuario A pide el incidente de B → 404
- El analista pide un incidente no asignado → 404
- Rol insuficiente → 403
- Registro con `"rol": "admin"` → se crea como `usuario`
- El reportante no recibe `notas_internas`

**Reglas de negocio**
- Transición inválida → 409 · `en_analisis` sin analista → 409
- El reportante edita fuera de `abierto` → 409
- Un incidente borrado no aparece en los listados

**Validación**
- Campos fuera de rango o enum inválido → 422 · `limite` > 100 → 422

Objetivo de cobertura: ≥ 80%.

## 10. Postman

- Entornos `local` y `produccion` (`url_base`)
- Script de post-login que guarda `token_acceso` y `token_refresco`
- Carpetas por rol (usuario, analista, admin) con casos positivos y negativos
- Exportada en `postman/` dentro del repo

## 11. Despliegue

**Local:** `docker compose up` levanta `api` + `db`.

**Producción (Dokploy):** un único servicio Docker Compose con dos contenedores.
- `db` (postgres): **volumen con nombre** para los datos y **sin puerto publicado**.
- `api`: aplica las migraciones de Alembic al arrancar y Traefik la expone con HTTPS.
- Variables de entorno configuradas en Dokploy, no en el repo.
- **Backup:** `pg_dump` programado, porque Dokploy no respalda una BD que vive dentro de un compose.

**CI (GitHub Actions)** en cada push: `ruff` → `bandit` → `pip-audit` → `pytest` contra un
Postgres de servicio.
