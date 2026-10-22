# Umbral — documentación del proyecto

> **Umbral** es la plataforma de **Kaelum Security**, un proveedor ficticio de ciberseguridad
> gestionada (MSSP). Proyecto académico de *Puesta en producción segura*: ninguna empresa,
> cliente ni servicio es real.
>
> Estado a 2026-10-15. En producción en un VPS propio con Dokploy.

---

## Índice

1. [Qué es y para quién](#1-qué-es-y-para-quién)
2. [Recorrido por la aplicación](#2-recorrido-por-la-aplicación)
3. [Arquitectura](#3-arquitectura)
4. [Tecnologías](#4-tecnologías)
5. [Autenticación: JWT y refresh tokens propios](#5-autenticación-jwt-y-refresh-tokens-propios)
6. [Roles y permisos](#6-roles-y-permisos)
7. [Multiempresa: aislamiento entre clientes](#7-multiempresa-aislamiento-entre-clientes)
8. [Incidencias](#8-incidencias)
9. [Sensores: señuelo y generador](#9-sensores-señuelo-y-generador)
10. [Qué datos recoge y cuánto tiempo los guarda](#10-qué-datos-recoge-y-cuánto-tiempo-los-guarda)
11. [Auditoría](#11-auditoría)
12. [Seguridad aplicada, capa a capa](#12-seguridad-aplicada-capa-a-capa)
13. [OWASP Top 10](#13-owasp-top-10)
14. [Despliegue](#14-despliegue)
15. [Pruebas: unitarias, integración, E2E y CI](#15-pruebas-unitarias-integración-e2e-y-ci)
16. [Datos de demostración](#16-datos-de-demostración)
17. [Decisiones y contrapartidas](#17-decisiones-y-contrapartidas)
18. [Referencia rápida](#18-referencia-rápida)

---

## 1. Qué es y para quién

Kaelum Security vigila la red de pequeñas y medianas empresas. Umbral reúne en una sola
aplicación tres cosas:

| Pieza | Qué resuelve |
|---|---|
| **Gestión de incidencias** | Los trabajadores de un cliente reportan una sospecha (un correo raro, un portátil lento). Un analista de Kaelum la investiga y la lleva hasta el cierre. |
| **Centro de seguridad** | Los sensores desplegados en cada cliente detectan sondeos de internet. El panel los muestra en tiempo real; un analista hace el triaje y convierte lo grave en incidencia. |
| **Administración multicliente** | Alta de clientes y de sus usuarios, con aislamiento estricto: una empresa nunca ve nada de otra. |

**Tres tipos de persona** usan la aplicación:

- **Trabajador de un cliente** (rol `usuario`, con empresa): reporta incidencias y sigue las suyas.
- **Analista de Kaelum** (rol `analista`, sin empresa): investiga las incidencias que tiene asignadas.
- **Administrador de Kaelum** (rol `admin`, sin empresa): ve todos los clientes, gestiona cuentas,
  hace el triaje de eventos y revisa la auditoría.

**Vocabulario fijo** en toda la interfaz:

- **Incidencia**: un ticket que abre una persona (o un admin a partir de un evento).
- **Evento**: algo que detecta un sensor de forma automática.

---

## 2. Recorrido por la aplicación

### Web pública (`/`)

La página de venta de Kaelum Security. Solo la ve quien no ha iniciado sesión.

- Presentación, los cuatro servicios (sensores señuelo, monitorización, gestión de incidencias,
  trazabilidad) y «cómo funciona» en tres pasos.
- **Planes** (precios orientativos, sin cobros reales):

  | Plan | Precio | Para quién |
  |---|---|---|
  | Esencial | 290 €/mes | Pymes que empiezan: 1 sensor, hasta 10 usuarios |
  | Profesional | 690 €/mes | Datos sensibles: 3 sensores, analista asignado, 24/7 en críticos |
  | Empresa | A medida | Varias sedes, SLA propio |

- Clientes de muestra, contacto (`comercial@kaelum.example`, dominio reservado) y un aviso visible
  de que la empresa es ficticia.

### Acceso (`/login`)

Email y contraseña. Tras entrar, el admin aterriza en el **Panel**, el resto en sus
**Incidencias**, y una cuenta **pendiente** (registrada, aún sin empresa) en **Unirme a mi
empresa**, la única pantalla que puede ver.

### Registro (`/registro`) y unión a una empresa (`/unirse`)

1. Cualquiera crea una cuenta con email y contraseña. Nace como `usuario` **sin empresa**.
2. Al entrar, solo ve «Unirme a mi empresa». Introduce el **código de invitación** que le da el
   gestor de su empresa (`XXXX-XXXX-XXXX`, da igual mayúsculas o guiones).
3. Desde ese momento es un trabajador de esa empresa, con el mismo token: la empresa se lee de la
   base de datos en cada petición.

### Consola

```
UMBRAL · Kaelum Security
INCIDENCIAS            (todos)   Incidencias · Reportar incidencia
CENTRO DE SEGURIDAD    (admin)   Panel · Eventos · Sensores
ADMINISTRACIÓN         (admin)   Clientes · Usuarios · Auditoría
(abajo)                          usuario · Mi cuenta · Cerrar sesión
```

| Pantalla | Qué hace |
|---|---|
| **Incidencias** | Listado con contadores (abiertas, en análisis, resueltas, críticas), filtros por estado, severidad, categoría y, para el admin, cliente. |
| **Reportar incidencia** | Formulario: título, descripción, severidad y categoría. |
| **Detalle** | Datos, estado y transiciones, asignación de analista, notas internas y, si viene de un evento, el evento de origen. |
| **Panel** | Indicadores (eventos del periodo, última hora, orígenes únicos, críticos), gráficas por tiempo, tipo, severidad e IP, y el **feed en vivo** con triaje. Selector de cliente y de periodo (1 h, 24 h, 7 días). |
| **Eventos** | Historial paginado con filtros (cliente, tipo, severidad, triaje, IP). Aviso de eventos nuevos llegados desde la última carga. |
| **Sensores** | Cada sensor, de qué cliente es, su último evento y sus totales. Se marca **silencioso** si lleva 15 minutos sin enviar nada. |
| **Clientes** | Alta (el código se sugiere a partir del nombre), edición y baja o reactivación. |
| **Usuarios** | Alta con rol, cliente y contraseña inicial (generador criptográfico), cambio de rol, activar o desactivar y restablecer contraseña. |
| **Auditoría** | Registro de acciones sensibles, filtrable por tipo, con alertas y cambios de privilegio resaltados. |
| **Mi cuenta** | Cambio de la propia contraseña, exigiendo la actual. |

---

## 3. Arquitectura

```
                          Internet
                             │
                       ┌─────┴──────┐  Traefik (Dokploy): TLS con Let's Encrypt
                       │   proxy    │
                       └─┬───┬────┬─┘
             host web /  │   │/api│            host del señuelo /
                         ▼   ▼    │                    ▼
                    ┌─────┐ ┌─────┴──┐           ┌──────────┐
     navegador ───► │ web │ │  api   │ ◄──────── │ señuelo  │  (eventos reales)
                    └─────┘ └──┬─────┘ ◄──────── │generador │  (eventos de demo)
                  estáticos    │                 └──────────┘
                               ▼
                          ┌─────────┐   ┌────────┐
                          │Postgres │◄──│ backup │  pg_dump diario
                          └─────────┘   └────────┘
```

| Servicio del compose | Papel | Expuesto |
|---|---|---|
| `web` | nginx sin privilegios que sirve el Angular compilado y la CSP | Sí, `/` del dominio web |
| `api` | FastAPI: toda la lógica, permisos y auditoría | Sí, `/api` del mismo dominio |
| `db` | PostgreSQL 17 | No |
| `senuelo` | Honeypot de registro | Sí, dominio propio |
| `generador` | Telemetría de demostración | No |
| `backup` | `pg_dump` periódico a un volumen | No |

**Mismo origen**: front y API comparten dominio (`/` y `/api`), así que no hace falta CORS para
la aplicación propia. La API quita el prefijo `/api` ella misma (middleware `QuitarPrefijo`),
porque Dokploy no genera el *strip path* para dominios con ruta.

**Código**: un directorio por servicio. `backend/` (API), `frontend/` (Angular y su nginx),
`senuelo/` (sensores), más `postman/`, `scripts/` y `docs/`. Mapa completo en el
[`README`](../README.md#estructura-del-repositorio).

**Capas del backend** (`backend/app/`):

```
routers/        HTTP y validación de entrada. Sin lógica
servicios/      Reglas de negocio y permisos, en un solo sitio, y auditoría
repositorios.py Acceso a datos (SQLAlchemy). Sin reglas
modelos.py      Tablas
esquemas.py     Entrada y salida (Pydantic), siempre separadas
seguridad.py    argon2, emisión y verificación de JWT, refresh tokens
dependencias.py Quién eres (token) y qué rol necesitas
```

---

## 4. Tecnologías

### Backend

| Tecnología | Versión | Para qué |
|---|---|---|
| Python | 3.12 | Lenguaje |
| FastAPI | ≥ 0.142 | API REST asíncrona |
| SQLAlchemy (async) + asyncpg | ≥ 2.1 | ORM y driver de PostgreSQL |
| Alembic | ≥ 1.20 | Migraciones (`0001` a `0007`) |
| Pydantic + pydantic-settings | ≥ 2.13 | Validación y configuración por entorno |
| PyJWT | ≥ 2.15 | Emitir y verificar los tokens de acceso (HS256) |
| argon2-cffi | ≥ 25.1 | Hash de contraseñas (Argon2id) |
| slowapi | ≥ 0.1.10 | Límite de peticiones |
| uvicorn | ≥ 0.54 | Servidor ASGI |
| uv | — | Gestión de dependencias con lockfile |

### Frontend

| Tecnología | Versión | Para qué |
|---|---|---|
| Angular | 21 | SPA con componentes *standalone*, señales y `OnPush` |
| Angular CDK | 21 | Overlays de los desplegables |
| RxJS | 7.8 | Peticiones HTTP |
| TypeScript | 5.9 | Lenguaje |
| Fuentes empaquetadas | — | Cormorant Garamond, Manrope y JetBrains Mono, sin Google Fonts |

Estilo visual «Lemarchand»: fondo oscuro, rojo sangre y oro, superficies de cristal, sin líneas
divisorias y glifos animados de fondo.

### Infraestructura

| Pieza | Para qué |
|---|---|
| Docker / Docker Compose | Imágenes multi-stage y orquestación |
| Dokploy + Traefik | Despliegue, dominios `sslip.io` y TLS con Let's Encrypt |
| PostgreSQL 17 | Base de datos |
| nginx-unprivileged 1.31 | Servir el front sin root |
| GitHub Actions | Integración y despliegue continuos (CI/CD) |

### Sensores

Python 3.12 con **solo la librería estándar** (`http.server`, `urllib`, `re`): ninguna
dependencia de terceros que mantener ni auditar.

---

## 5. Autenticación: JWT y refresh tokens propios

### Flujo de entrada

```
navegador                                                         API de Umbral
   │ POST /api/auth/web/login  {email, contrasena}  ─────────────────►│
   │                                       comprueba la contraseña    │
   │                                       (argon2), cuenta activa y  │
   │                                       empresa de alta            │
   │ ◄── 200 {token_acceso}  +  Set-Cookie: __Secure-refresco ────────│
   │ GET /api/usuarios/yo  (Authorization: Bearer <token_acceso>) ───►│
```

| Pieza | Qué es | Dónde vive | Vida |
|---|---|---|---|
| **Token de acceso** | JWT HS256 con `sub`, `tipo`, `ver`, `iat`, `exp` y `jti` | Solo en memoria (una señal de Angular) | 15 min |
| **Token de refresco** | 48 bytes aleatorios; en la BD solo su SHA-256 | Cookie `__Secure-refresco`: `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/api/auth/web` | 7 días |
| **Contraseña** | Argon2id | Tabla `usuarios` | — |

- **El token dice quién eres; nuestra BD dice qué puedes hacer**: rol, empresa y si la cuenta
  está activa se leen en **cada** petición. El token no lleva el rol, así que un cambio de rol es
  inmediato.
- **Mismo tiempo de respuesta exista o no el email**: si no existe, se verifica contra un hash
  ficticio. Un login fallido no revela qué cuentas hay.
- El login está limitado a **5 intentos por minuto e IP**, y cada fallo queda auditado
  (`login_fallido`).

### Refresco: rotación y detección de reutilización

Cada `POST /auth/web/refrescar` **revoca** el token de refresco usado y emite uno nuevo de la misma
*familia*. Si llega uno ya revocado, alguien tiene una copia (la víctima o el atacante, no se sabe
cuál), así que:

1. Se revoca **toda la familia**: ninguno de los dos puede seguir refrescando.
2. Se sube la **versión de sesión** del usuario: el token de acceso que el atacante obtuvo con su
   copia deja de valer **al momento**, sin esperar a que caduque.
3. Queda en la auditoría como `reutilizacion_token`.

Los otros dispositivos del usuario tienen su propia familia: se recuperan con un refresco, sin
volver a entrar.

En el navegador, el interceptor hace **un único refresco a la vez**. Si varias peticiones reciben
un 401 a la vez, todas esperan al mismo. Dos refrescos en paralelo enviarían la misma cookie dos
veces y la API lo tomaría, con razón, por una reutilización.

### Revocación inmediata: la versión de sesión

Un JWT no se puede «despublicar»: vale hasta que caduca. Para que cambiar la contraseña eche de
verdad a quien tuviera una sesión robada, cada usuario tiene un entero `version_sesion` que viaja
en el token como claim `ver`. La API ya lee el usuario de la BD en cada petición, así que
comprobarlo no cuesta ninguna consulta extra: un token con una versión vieja recibe un 401.

| Operación | Revoca refresh tokens | Sube la versión (el access cae ya) |
|---|---|---|
| Cambiar la propia contraseña | Sí | Sí |
| Restablecer contraseña (admin) | Sí | Sí |
| Desactivar (admin) | Sí | Sí (reactivar no resucita los tokens de antes) |
| Reutilización de un refresh | La familia | Sí |
| `crear-admin` sobre una cuenta existente | Sí | Sí |
| Cambiar el rol | No | No: el rol no va en el token, se lee de la BD en cada petición |
| Dar de baja un cliente | Los de sus usuarios | No hace falta: la empresa se comprueba en cada petición |
| Cerrar sesión | La familia de ese dispositivo | No |

### Persistencia

| Se comprueba en los E2E | Resultado |
|---|---|
| Local Storage y Session Storage | Vacíos |
| `document.cookie` | Vacío: la cookie es `HttpOnly` |
| Cookies del navegador | Solo `__Secure-refresco`, con `HttpOnly`, `Secure`, `SameSite=Strict` y `Path=/api/auth/web` |
| Recargar la página | La sesión se recupera con un refresco |
| Cerrar sesión y recargar | Pide entrar otra vez |

Un XSS no encuentra un token de acceso guardado que robar, ni puede leer la cookie. Lo que sí
podría es usar la sesión mientras la página está abierta: por eso la CSP estricta es la primera
línea, no la cookie.

### Configuración

| Variable | Secreta | Notas |
|---|---|---|
| `JWT_SECRETO` | **Sí** | Mínimo 32 caracteres: la API no arranca con menos. Quien la tenga puede fabricar un token de cualquier usuario, admin incluido |
| `COOKIE_REFRESCO_RUTA` | No | `/api/auth/web` en el compose: el `Path` tal como lo ve el navegador |
| `ACCESO_MINUTOS`, `REFRESCO_DIAS` | No | 15 y 7 por defecto |
| `MFA_CLAVE` | **Sí** | Mínimo 32 caracteres. Cifra los secretos TOTP en la BD. Distinta de `JWT_SECRETO`. Si se pierde, ningún MFA vuelve a validar |
| `MFA_OBLIGATORIO_PERSONAL` | No | `true`: admin y analista no ven nada hasta activar el MFA |
| `URL_PUBLICA` | No | `https://dominio-de-la-web`, sin barra final. Vacía = sin Google ni GitHub |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | El secreto, **sí** | Activan «Continuar con Google» |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | El secreto, **sí** | Activan «Continuar con GitHub» |
| `COOKIE_OAUTH_RUTA` | No | `/api/auth/oauth` en el compose |

### Verificación en dos pasos (TOTP)

TOTP (RFC 6238) con cualquier app de autenticación. El login pasa a tener dos pasos:

```
POST /auth/web/login  {email, contraseña}  →  {mfa_requerido, desafio}   (sin token ni cookie)
POST /auth/web/mfa    {desafio, codigo}    →  {token_acceso} + cookie de refresco
```

El **desafío** es un JWT de 5 minutos con `tipo: "mfa"` y la versión de sesión: no sirve como
Bearer, y deja de valer si entre medias cambia la contraseña o se cierran las sesiones.

| Garantía | Cómo |
|---|---|
| Una copia de la BD no basta para generar códigos | El secreto se guarda cifrado con AES-GCM (clave derivada de `MFA_CLAVE` con HKDF) y con el id del usuario como dato asociado: copiado a otra fila, no se descifra |
| Un código visto no se reutiliza | Se guarda el último paso de 30 s aceptado; el `UPDATE` es condicional y atómico, así que dos peticiones con el mismo código no pasan las dos |
| No se prueba el millón de códigos | 5/min por IP y, además, 5 fallos seguidos bloquean la cuenta 15 minutos, cambie o no la IP. El contador se suma en la propia BD |
| Desfase de reloj | Se aceptan el paso anterior, el actual y el siguiente (±30 s) |
| Sin el móvil | 10 códigos de recuperación de un solo uso (solo su hash en la BD). Se pueden regenerar |
| Un token robado no cambia cómo se entra | Activar el MFA, vincular o desvincular un proveedor pide una prueba fresca: la contraseña; sin contraseña, un código MFA o un login de hace menos de 5 min (claim `aut` del token, que se hereda al refrescar). Falla en cerrado: 403 «vuelve a iniciar sesión». Desactivar o regenerar pide además un código |
| Ningún método de entrada se lo salta | Google y GitHub también acaban en el desafío si la cuenta tiene MFA |

El **personal** (admin y analista) está obligado: hasta activarlo, cualquier ruta que no sea su
cuenta responde 403 y la web le lleva a `/activar-mfa`. No puede desactivarlo. Si alguien pierde
el móvil y los códigos, un admin le quita el MFA desde Usuarios (cierra sus sesiones); comprobar
que es quien dice ser queda fuera de la app.

### Google y GitHub (OAuth 2.0 + PKCE)

El flujo lo resuelve la API: el navegador nunca ve un token del proveedor, y la sesión que se
abre es la misma de siempre (cookie de refresco propia).

```
/auth/oauth/{p}/inicio    → cookie __Secure-oauth (state + verificador PKCE, firmada, 10 min)
                          → 302 al proveedor con code_challenge (S256) y state
/auth/oauth/{p}/callback  → compara el state con el de la cookie, canjea el código, lee la
                            identidad, abre sesión (o desafío MFA) y vuelve al front
```

| Riesgo | Defensa |
|---|---|
| Login CSRF (colar el código del atacante) | `state` aleatorio ligado a la cookie de ese navegador, comparado en tiempo constante. Un fallo queda auditado (`oauth_estado_invalido`) |
| Robo del código en la redirección | PKCE S256 y `client_secret`: el código solo no sirve |
| Identidad por email | Se busca SIEMPRE por (proveedor, `sub`). El email del proveedor puede cambiar o reasignarse |
| Email ajeno sin verificar | Una cuenta solo nace de un email verificado (`email_verified` en Google; principal y verificado en `/user/emails` en GitHub) |
| **Pre-account hijacking** | El registro público no verifica emails: alguien podría registrar antes el de la víctima con su propia contraseña. Por eso un email que ya existe **no se vincula solo** (`?error=oauth_email`). Se vincula desde Mi cuenta, con sesión abierta y la contraseña |
| Cookie del flujo | `HttpOnly`, `Secure`, `Path=/api/auth/oauth`, 10 min, un solo uso. `SameSite=Lax` y no `Strict`: la vuelta desde el proveedor es una navegación de otro sitio |
| Desafío MFA tras OAuth | Va en el fragmento (`/login#mfa=…`): no llega al servidor ni a los logs, y el front lo borra de la URL |

Una cuenta nacida de Google o GitHub entra como en el registro público: rol `usuario`, sin
empresa y sin contraseña (`hash_contrasena = "!"`, que nunca valida). No puede quedarse sin
ninguna forma de entrar: desvincular el último proveedor de una cuenta sin contraseña da 409.

**Alta en los proveedores.** Callback exacto: `{URL_PUBLICA}/api/auth/oauth/google/callback` y
`…/github/callback`. Google: cliente OAuth «Aplicación web», alcances `openid email`. GitHub:
OAuth App con permiso de lectura de emails.

### Historia: de Firebase a la autenticación propia

Entre el 14 y el 15 de octubre la identidad estuvo en Firebase Authentication (migraciones
`0005` y `0006`). Se volvió a la autenticación propia para tener el control completo de la
rotación, la revocación y la auditoría de los intentos fallidos. Las contraseñas que guardaba
Firebase no se pueden traer: la migración `0006` deja a todas las cuentas sin contraseña válida, y
el primer admin se recupera con `crear-admin`.

---

## 6. Roles y permisos

| Acción | usuario | gestor | analista | admin |
|---|---|---|---|---|
| Reportar incidencia | ✅ | ✅ | ✅ | ✅ |
| Ver incidencias | las suyas | **todas las de su empresa** | las asignadas y las suyas | todas |
| Editar título, descripción y categoría | las suyas, solo en `abierto` | las suyas, solo en `abierto` | ❌ | ✅ |
| Notas internas (ver y escribir) | ❌ | ❌ | las asignadas | ✅ |
| Cambiar estado | ❌ | ❌ | las asignadas | ✅ |
| Asignar analista, reabrir y borrar | ❌ | ❌ | ❌ | ✅ |
| Código de invitación de su empresa (ver y regenerar) | ❌ | ✅ | ❌ | ✅ (de todas) |
| Desactivar y restablecer la contraseña de… | ❌ | los `usuario` de su empresa | ❌ | cualquiera |
| Sensores | ❌ | los de su empresa | ❌ | todos |
| Panel, eventos y triaje | ❌ | ❌ | ❌ | ✅ |
| Clientes, usuarios y auditoría | ❌ | ❌ | ❌ | ✅ |

Una cuenta **pendiente** (registrada, sin empresa) solo puede ver su cuenta, cambiar su
contraseña y unirse a una empresa. Todo lo demás le devuelve 403, en la API, no solo en la web.

El gestor **no** toca a otro gestor (sería hacerse con la empresa), ni a nadie de fuera de su
empresa, ni al personal de Kaelum: para todos ellos, 404. Solo un admin crea gestores, dándolos de
alta con su empresa o ascendiendo a un trabajador.

Política de respuestas:

- **404** si no puedes **ver** el recurso: no se confirma que exista.
- **403** si lo ves pero no puedes hacer esa acción.
- **409** si puedes, pero el estado actual no lo permite.

La interfaz solo **oculta** lo que no te corresponde. Quien autoriza es siempre la API.

---

## 7. Multiempresa: aislamiento entre clientes

### Modelo

- Tabla `empresas`: `codigo` (identificador estable, p. ej. `transportes-ibarra`, no editable),
  `nombre`, `sector`, `activa`.
- `empresa_id` en `usuarios`, `incidentes` y `eventos_seguridad`.
- `codigo_invitacion` en `empresas`: 12 símbolos de un alfabeto sin caracteres ambiguos (~59
  bits), único y regenerable.
- Quién es **personal de Kaelum** lo decide el **rol** (`admin` o `analista`, siempre sin
  empresa), **nunca** la ausencia de empresa. Un `usuario` o `gestor` sin empresa es una cuenta
  **pendiente**, que no ve nada de nadie. Si «sin empresa» significara «personal», cualquiera que
  se registrara vería a todos los clientes; `test_gestor.py` lo comprueba también saltándose la
  dependencia que lo bloquea, para que la segunda barrera no dependa de la primera.

### Reglas

| Regla | Cómo se impone |
|---|---|
| Admin y analista nunca tienen empresa | Alta con empresa → 422. Ascender a un usuario de cliente → 409 |
| Una incidencia es del cliente de quien la reporta | Se copia al crearla; si viene de un evento, se copia del evento |
| Un usuario de cliente solo ve lo de su empresa | Comprobación de empresa **antes** que la de rol (defensa en profundidad) |
| El filtro de empresa no se puede saltar | A un usuario de cliente se le fija la suya, mande lo que mande en `?empresa_id=` |
| Dar de baja un cliente | Sus usuarios pierden el acceso en la petición siguiente |
| Un analista asignado ha de ser de Kaelum | Asignar un usuario de cliente → 422 |

**Defensa en profundidad, probada**: un test falsea a propósito el reportante de una incidencia
de *Clínica Solana* para que apunte a un usuario de *Transportes Ibarra*. La comprobación de
empresa la sigue ocultando.

---

## 8. Incidencias

### Ciclo de vida

```
abierto ──► en_analisis ──► resuelto ──► cerrado
   ▲                                       │
   └──────────── reapertura (solo admin) ──┘
```

- Cualquier otra transición se rechaza con **409**.
- Pasar a `en_analisis` exige tener un analista asignado.
- En cuanto sale de `abierto`, el reporte original queda congelado como evidencia: el reportante
  ya no puede editarlo.
- El borrado es **lógico** (`borrado_en`): el registro se conserva y deja de aparecer.

### Campos

| Campo | Valores |
|---|---|
| Severidad | `baja`, `media`, `alta`, `critica` |
| Categoría | `phishing`, `malware`, `acceso_no_autorizado`, `fuga_datos`, `denegacion_servicio`, `otro` |
| Notas internas | Solo las ven el analista asignado y el admin; nunca llegan al reportante |

### Desde un evento

Un admin puede abrir una incidencia desde un evento. Se rellena sola: título, descripción con IP,
petición, servicio y fecha, severidad del evento y una categoría deducida del tipo. El evento
queda enlazado y pasa a «revisado».

---

## 9. Sensores: señuelo y generador

Los dos son la misma imagen; la variable `MODO` elige el papel.

### Señuelo (`MODO=senuelo`)

Un **honeypot de registro**, no de interacción: está expuesto a internet y **no es vulnerable**.

- A toda petición responde el mismo `404 Not Found` y se anuncia como `nginx`, sin delatar que es
  un señuelo.
- No sirve ficheros, no ejecuta nada y no lee el cuerpo de la petición.
- Clasifica la petición y la envía a la API en lotes (cada 20 eventos o cada 3 segundos).
- Declara de qué cliente es con `EMPRESA` (código del cliente).
- Cada 5 minutos escribe en su log un resumen: eventos entregados y perdidos.

Internet lo sondea sola, sin parar: de ahí sale el tráfico **real** del panel.

### Generador (`MODO=generador`)

**Telemetría de demostración**: fabrica peticiones que imitan el ruido de sondeo típico de un
servidor público (rutas de WordPress, `.env`, inyecciones de libro, escáneres conocidos) y las
reparte entre los clientes de `EMPRESAS`. No envía tráfico a ningún sitio: solo crea registros
para que el panel tenga datos durante una demo. Las IP de origen salen sobre todo de rangos de
documentación (RFC 5737).

### Clasificador (`senuelo/clasificador.py`)

Reglas tipo WAF por expresiones regulares. La primera que coincide manda:

| Tipo | Detecta | Severidad |
|---|---|---|
| `recorrido_rutas` | `../`, `/etc/passwd`, sus variantes codificadas | alta |
| `inyeccion` | `UNION SELECT`, `' OR '1'='1`, `<script`, `sleep()`… | alta |
| `fichero_sensible` | `.env`, `.git`, `wp-config.php`, `id_rsa`, copias `.bak`/`.sql`… | crítica |
| `sondeo_rutas` | `wp-admin`, `phpmyadmin`, `cgi-bin`, `jenkins`… | media |
| `fuerza_bruta` | `POST` a rutas de login | media |
| `escaner` | User-agent de herramientas (`sqlmap`, `nikto`, `nmap`, `nuclei`, `curl`…) | baja |
| `otro` | Todo lo demás | baja |

El generador usa el mismo clasificador: un evento inventado se etiqueta igual que uno real.

### Ingesta en la API

- `POST /eventos` con la cabecera `X-Ingesta-Token`, comparada en tiempo constante. No es un token
  de usuario: lo comparten solo los servicios del compose.
- Lotes de 1 a 100 eventos.
- Todo lo que viene de internet se **trunca y limpia**: se quitan los caracteres de control (evita
  inyección en logs), la ruta y el agente se cortan a 512 caracteres y la IP se valida.
- Un código de empresa desconocido rechaza el lote entero con 422. Mejor que se vea al momento en
  el log del sensor que llenar el panel de eventos sin dueño.
- Cada evento nuevo se difunde por **SSE** a los paneles abiertos. Como `EventSource` no deja
  enviar `Authorization`, el front lee el stream con `fetch`. El servidor cierra cada 10 minutos
  para obligar a reautenticarse.

### Triaje

Cada evento tiene un estado (`nuevo`, `revisado` o `ignorado`) y una nota. El triaje se refleja
en vivo en los paneles de todos los admins. Los campos que vienen de internet no se editan nunca.

---

## 10. Qué datos recoge y cuánto tiempo los guarda

| Dato | De dónde | Retención |
|---|---|---|
| Email, rol, empresa y estado de cada cuenta | Alta por un admin | Mientras exista la cuenta |
| Contraseñas | Solo su hash Argon2id, nunca en claro | Mientras exista la cuenta |
| Tokens de refresco | Solo su SHA-256, con su caducidad y revocación | Indefinida (filas pequeñas; las caducadas no sirven de nada) |
| Incidencias (texto, severidad, notas) | Usuarios y analistas | Indefinida; el borrado es lógico |
| Eventos: IP de origen, método, ruta, user-agent, servicio, cliente y fecha | Sensores | **30 días** (`EVENTOS_RETENCION_DIAS`), salvo los enlazados a una incidencia, que son evidencia |
| Auditoría: quién, qué acción, sobre qué recurso, IP y fecha | La propia API | Indefinida |
| Copias de seguridad | `pg_dump` diario | 7 días |

- La purga de eventos se reparte en el tiempo: se ejecuta, de media, una de cada 200 ingestas, sin
  necesidad de cron.
- La IP de quien sondea el señuelo es un dato personal (RGPD). Se guarda con una finalidad de
  seguridad y con un plazo acotado.
- Ningún dato se envía a terceros: ni proveedor de identidad externo, ni analítica, ni fuentes de Google.

---

## 11. Auditoría

Cada acción sensible deja un registro con usuario, acción, recurso, IP y fecha.

| Grupo | Acciones |
|---|---|
| Sesión | `login`, `login_fallido`, `logout`, `reutilizacion_token` |
| Cuentas | `crear_usuario`, `restablecer_contrasena`, `cambio_contrasena`, `cambio_contrasena_fallido`, `cambio_rol`, `desactivar_usuario`, `reactivar_usuario`, `crear_admin_cli` |
| Clientes | `crear_empresa`, `editar_empresa` |
| Incidencias | `crear_incidente`, `editar_incidente`, `cambio_estado`, `asignar_incidente`, `editar_notas`, `borrar_incidente` |
| Eventos | `triaje_evento` |

Registro e invitaciones: `registro`, `registro_duplicado` (alerta: alguien prueba emails),
`unirse_empresa`, `union_empresa_fallida` (alerta: posible fuerza bruta del código) y
`regenerar_codigo_invitacion`.

La IP real llega por `X-Forwarded-For` de Traefik. Uvicorn solo se fía de esa cabecera porque la
API no publica ningún puerto: no hay otro camino que el proxy.

---

## 12. Seguridad aplicada, capa a capa

### Identidad y acceso

- JWT propio de 15 minutos, refresh tokens rotados con detección de reutilización y
  revocación inmediata por versión de sesión.
- Rol, empresa y estado de la cuenta leídos de la BD, nunca del token.
- Registro público con 5 intentos/min, mismo mensaje exista o no el email y hash calculado
  siempre (mismo tiempo de respuesta). La cuenta nace sin empresa y sin ver nada.
- Código de invitación con ~59 bits, 5 intentos/min y regenerable; un gestor nunca se une por
  código (si pudiera, un código filtrado le daría una empresa ajena).
- Contraseñas de 12 caracteres como mínimo. El generador del alta usa `crypto.getRandomValues`.
- Contraseñas con Argon2id. Login y cambio de contraseña limitados a **5 intentos por minuto**;
  cambiar la propia exige la actual.

### API

- Esquemas de entrada con `extra="forbid"`: nadie puede colar `rol`, `estado` o `reportante_id`.
- Esquemas de salida según quien pregunta: las notas internas nunca llegan al reportante.
- Control de IDOR en cada acceso, con 404 para lo ajeno.
- Paginación con límite máximo (100) en todos los listados.
- Búsqueda de email con `LIKE` escapado: un `%` del cliente se busca literal.
- Errores sin trazas: la traza va al log del servidor, nunca al cliente.
- `/docs` y `/openapi.json` desactivados en producción.
- Cabeceras: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options: DENY`,
  `Referrer-Policy` y CSP.
- CORS con lista blanca por variable de entorno, nunca `*`.

### Navegador

- **CSP estricta** sin `'unsafe-inline'`: nonce por respuesta para los estilos de Angular,
  **Trusted Types**, y `connect-src` cerrado al propio dominio.
- Estilos dinámicos aplicados por el CSSOM, no con atributos `style`.
- Token de acceso solo en memoria; el de refresco, en una cookie `HttpOnly` y `SameSite=Strict`.
  Fuentes servidas desde el propio dominio.

### Contenedores y red

| Medida | Dónde |
|---|---|
| Imágenes slim multi-stage, sin herramientas de build | `backend/Dockerfile`, `frontend/Dockerfile` |
| Usuario sin privilegios (uid 10001 en la API, nginx-unprivileged en el front) | `backend/Dockerfile`, `frontend/Dockerfile` |
| Sistema de ficheros de solo lectura, `/tmp` en memoria | `docker-compose.yml` |
| `cap_drop: ALL` y `no-new-privileges` | `docker-compose.yml` |
| PostgreSQL sin puerto publicado | `docker-compose.yml` |
| Sin cabecera `Server` (`--no-server-header`) | `backend/Dockerfile` |
| `JWT_SECRETO` solo llega al servicio `api` | `docker-compose.yml` |

### Secretos

- Nunca en el repositorio: se configuran en Dokploy.
- `.gitignore` cubre `.env` y los JSON de cuentas de servicio (`*-adminsdk-*.json`).
- Rotar `JWT_SECRETO` invalida todos los tokens de acceso a la vez: es el botón de emergencia si se
  filtra.

---

## 13. OWASP Top 10

Correspondencia entre las categorías del **OWASP Top 10:2025** y lo que hace Umbral. Conviene
comprobar la versión vigente en <https://owasp.org/Top10/>.

| Categoría | Riesgo | Cómo se mitiga en Umbral | Dónde mirar |
|---|---|---|---|
| **A01 Broken Access Control** | Ver o tocar lo que no es tuyo (IDOR, escalada) | Permisos centralizados en los servicios; 404 para lo ajeno; aislamiento por empresa **antes** del rol; filtro de empresa forzado para clientes; rol leído de la BD en cada petición; esquemas de entrada sin `rol`, `estado` ni `reportante_id` | `backend/app/servicios/incidentes.py`, `backend/tests/test_empresas.py` |
| **A02 Security Misconfiguration** | Valores por defecto inseguros, información de más | `/docs` desactivado en producción; errores sin trazas; CSP, HSTS, `nosniff` y `DENY`; CORS con lista blanca; sin cabecera `Server`; contenedores de solo lectura y sin capabilities; la API no arranca con un `JWT_SECRETO` corto | `backend/app/main.py`, `frontend/nginx/cabeceras-seguridad.conf`, `docker-compose.yml` |
| **A03 Software Supply Chain Failures** | Dependencias vulnerables o comprometidas | Lockfiles (`uv.lock`, `package-lock.json`); `pip-audit --strict` y `npm audit` en CI; sensores sin dependencias; ningún SDK de terceros para la identidad; imágenes base fijadas | `.github/workflows/ci.yml` |
| **A04 Cryptographic Failures** | Secretos o datos sensibles mal protegidos | Contraseñas con Argon2id; refresh tokens guardados solo como SHA-256; JWT con algoritmo fijado (no acepta `alg=none`); TLS en todo; token de ingesta comparado en tiempo constante; secretos fuera del repo | `backend/app/seguridad.py`, `backend/app/routers/eventos.py` |
| **A05 Injection** | SQL, XSS, inyección en logs | ORM con parámetros enlazados; `LIKE` escapado; Angular escapa por defecto y la CSP con Trusted Types bloquea sumideros de DOM; los caracteres de control se quitan de lo que llega de internet | `backend/app/repositorios.py`, `backend/app/esquemas.py` |
| **A06 Insecure Design** | Fallos de diseño, no de código | Registro que nace sin privilegios (cuenta pendiente); personal del MSSP decidido por rol, no por la ausencia de empresa; borrado lógico (evidencia); reporte congelado al pasar a análisis; máquina de estados con 409; el señuelo no es explotable por diseño | `backend/app/servicios/`, `senuelo/` |
| **A07 Authentication Failures** | Credenciales débiles, sesiones robadas | Login con 5 intentos/min y tiempo constante; mínimo 12 caracteres; refresh rotado con detección de reutilización; revocación **inmediata** por versión de sesión al cambiar o restablecer la contraseña y al desactivar; access token solo en memoria y refresh en cookie `HttpOnly`; cambiar la contraseña exige la actual (5/min) | `backend/app/servicios/auth.py`, `backend/app/servicios/usuarios.py`, `frontend/src/app/core/sesion.ts` |
| **A08 Software or Data Integrity Failures** | Datos o código manipulados | La CI bloquea el merge si falla una comprobación; migraciones versionadas y probadas; los campos de un evento no se editan nunca, solo el triaje | `backend/tests/test_migraciones.py` |
| **A09 Logging & Alerting Failures** | No enterarse de un ataque | Auditoría de todas las acciones sensibles con IP real; el panel resalta alertas; el señuelo informa cada 5 minutos de entregados y perdidos; logins fallidos y reutilización de tokens auditados | `backend/app/servicios/auditoria.py` |
| **A10 Mishandling of Exceptional Conditions** | Errores que dejan el sistema en un estado inseguro | Manejador global que responde 500 genérico y registra la traza; fallos de verificación del token resueltos como 401 (se deniega, no se concede); los lotes de ingesta inválidos se rechazan enteros; un volcado de backup fallido no deja ficheros a medias | `backend/app/main.py`, `backend/app/seguridad.py` |

---

## 14. Despliegue

### Dominios (Dokploy)

| Dominio | Ruta | Servicio |
|---|---|---|
| `…-d84d64-51-77-145-58.sslip.io` | `/` | `web:8080` |
| el mismo | `/api` | `api:8000` |
| `…-bcaf63-51-77-145-58.sslip.io` | `/` | `senuelo:8000` |

### Variables de entorno

| Variable | Notas |
|---|---|
| `POSTGRES_PASSWORD` | Obligatoria |
| `JWT_SECRETO` | Obligatoria y **secreta**. Mínimo 32 caracteres |
| `MFA_CLAVE` | Obligatoria y **secreta**. Mínimo 32 caracteres, distinta de `JWT_SECRETO` |
| `URL_PUBLICA`, `GOOGLE_*`, `GITHUB_*` | Opcionales: login con Google y GitHub (sección 5) |
| `MFA_OBLIGATORIO_PERSONAL` | Por defecto `true` |
| `INGESTA_TOKEN` | Mínimo 32 caracteres. Vacía, la ingesta queda desactivada |
| `CORS_ORIGENES` | Opcional |
| `EMPRESA_SENUELO` | Por defecto `hotel-mirador` |
| `EMPRESAS_GENERADOR` | Por defecto, los tres clientes de demo |

### Puesta en marcha desde cero

1. Variables en Dokploy y despliegue del compose. Las migraciones se aplican al arrancar la API.
2. En el contenedor `api`:
   ```bash
   python -m app.cli crear-admin tu@email     # primer admin (pide la contraseña)
   python -m app.cli sembrar-demo             # clientes y datos de demostración
   ```
   `sembrar-demo` tiene que ir **antes** de que envíen los sensores; si no, sus lotes se rechazan
   porque las empresas aún no existen.

### Copias de seguridad

El servicio `backup` hace un `pg_dump` en formato custom cada 24 h, con permisos `600`, y borra
los de más de 7 días. Un volcado fallido no deja ficheros a medias. El volumen vive en la misma
máquina: protege de borrados accidentales, no de perder el servidor. Para tener copia fuera, hay
que configurar un *Volume Backup* hacia S3 en Dokploy.

---

## 15. Pruebas: unitarias, integración, E2E y CI

### Resumen

| Tipo | Herramienta | Qué prueba | Cantidad |
|---|---|---|---|
| **Unitarias de los sensores** | pytest | Clasificador del señuelo | 12 |
| **Integración de la API** | pytest + httpx + BD real | Cada endpoint por HTTP, con permisos y efectos en la BD | 183 |
| **Unitarias del front** | Vitest (`ng test`) | Sesión, interceptor, guardas, servicio de clientes, errores, utilidades | 53 |
| **E2E** | Playwright | Flujos completos en un navegador real contra la pila entera | 22 |
| **Colección de API** | Postman / Newman | Roles, registro e invitaciones, IDOR, tokens manipulados, refresh tokens, revocación, aislamiento, rate limit | 126 peticiones, 191 comprobaciones |
| **Seguridad estática** | ruff (reglas `S`), bandit | Código de la API | — |
| **Dependencias** | pip-audit, npm audit | Backend y front | — |

```bash
cd backend
uv run pytest --cov               # integración de la API (cobertura mínima 80 %)
uv run pytest ../senuelo          # unitarias del clasificador
cd ../frontend
npx ng test --watch=false         # unitarias del front
npx playwright test               # E2E (levanta todo solo)
```

### Tests de integración de la API

Cada test levanta la aplicación real en memoria y le habla por HTTP con `httpx`. En local la base
de datos es SQLite y en la CI un **PostgreSQL 17 real**. Se prueba el comportamiento que vería un
cliente (códigos, cuerpos y efectos en la BD), no funciones sueltas.

Ficheros en `backend/tests/`:

| Fichero | Qué cubre |
|---|---|
| `test_auth.py` | Login, mismo error exista o no el email, rate limit, sin token, firma manipulada, caducado, `alg=none`, token sin versión de sesión, rotación del refresh, reutilización (familia revocada y access del atacante tumbado al momento, otros dispositivos intactos), logout, rol desde la BD |
| `test_auth_web.py` | Cookie de refresco endurecida y nunca en el cuerpo, rotación de la cookie, reutilización, logout que la borra, `Path` configurable tras un proxy |
| `test_registro.py` | Registro público (sin rol ni empresa, mínimo 12 caracteres, email existente sin revelar nada, rate limit), cuenta pendiente que no ve nada, unión con código (formato flexible, inventado → 422 auditado, regenerado, empresa de baja, gestor nunca por código, rate limit) |
| `test_gestor.py` | Alcance del gestor: incidencias de su empresa y no de otra, sin notas internas, código de invitación, gestión solo de los `usuario` de su empresa, sensores propios; segunda barrera de aislamiento sin la dependencia |
| `test_empresas.py` | CRUD de clientes, reglas de miembros, **aislamiento** (leer, editar, cambiar estado, notas, listar y filtro forzado), defensa en profundidad con un reportante falseado, baja de un cliente, ingesta, resumen, sensores e incidencia desde evento por cliente |
| `test_incidentes.py` | Permisos por rol, IDOR, transiciones y 409, notas internas ocultas al reportante, borrado lógico, auditoría |
| `test_usuarios.py` | Filtros (incluido `LIKE` con comodines), altas, emails duplicados, cambio de contraseña y restablecimiento con revocación **inmediata** del access token, límite de 5/min, activar y desactivar (reactivar no resucita tokens viejos) |
| `test_eventos.py` | Token de ingesta (sin token, incorrecto, un JWT de admin no vale), limpieza y truncado, IP inválida, tamaño de lote, filtros, resumen y tramos, triaje, SSE solo para admin, incidencia desde evento |
| `test_migraciones.py` | Las migraciones coinciden con los modelos; el downgrade deja la BD vacía |
| `test_plataforma.py` | Salud, cabeceras de seguridad, CORS permitido y rechazado, error 422, prefijo `/api` |
| `test_demo.py` | Semilla idempotente, reparto por clientes, completado de una BD sembrada antes |

**Sin red.** Todo es local: el helper `cabeceras()` inicia sesión con `POST /auth/login` contra
la API real, con usuarios creados directamente en la BD de pruebas.

### Tests unitarios

**Sensores:** `senuelo/test_clasificador.py` prueba cada regla del WAF con ejemplos reales
(recorrido de rutas, inyección, ficheros sensibles, escáneres) y casos que no deben coincidir. El
resto de la lógica (máquina de estados, permisos, aislamiento) se prueba a través de la API, que
es donde importa: un permiso bien escrito pero mal enganchado al router no protege nada.

**Front** (`frontend/src/**/*.spec.ts`, Vitest con jsdom):

| Fichero | Qué cubre |
|---|---|
| `core/sesion.ts` → `sesion.spec.ts` | Token solo en memoria; **dos refrescos simultáneos hacen una sola petición**; restaurar sin cookie deja la sesión vacía; salir limpia aunque la API no responda |
| `core/interceptor.spec.ts` | Añade el Bearer; no lo envía a rutas públicas; ante un 401 refresca y repite una vez; varios 401 a la vez comparten el refresco; si el refresco falla, cierra la sesión y va al login; en `/api/auth/*` no refresca |
| `core/guardas.spec.ts` | Sesión obligatoria, solo invitados, solo admin y landing solo sin sesión |
| `core/clientes.spec.ts` | Caché de clientes (una sola carga, reintento si falla), nombres, opciones de filtro y de alta (sin clientes de baja) |
| `core/errores.spec.ts` | Mensajes por código, sin trazas de un 500; campos señalados por un 422 |
| `paginas/clientes.spec.ts` | El código sugerido de un cliente siempre lo acepta la API |

### E2E (Playwright)

`npx playwright test` levanta solo, sin Docker y sin tocar nada real
(`frontend/e2e/entorno.mjs`):

1. Compila el front **para producción**.
2. Crea una base de datos nueva, aplica las migraciones y siembra dos clientes, un admin y un
   trabajador de cada cliente y una gestora (`backend/tests/e2e_semilla.py`, que se niega a correr en
   producción).
3. Arranca la **API real** desde `backend/` con su autenticación propia. El rate limit va desactivado solo aquí:
   todas las pruebas entran desde `127.0.0.1` y lo cubre `test_auth.py`.
4. Sirve el build con **exactamente las mismas cabeceras que nginx**, leídas de
   `nginx/cabeceras-seguridad.conf` (CSP con nonce y Trusted Types incluidos), y reenvía `/api` a
   la API como hace Traefik.

Cada prueba **falla si el navegador registra una violación de la CSP o de Trusted Types, un error
de JavaScript o un diálogo inesperado** (fixture `vigilancia` en `e2e/ayudas.ts`). Así, todos los
flujos verifican de paso que la política de seguridad de producción no rompe la app.

| Fichero | Escenarios |
|---|---|
| `acceso.spec.ts` | La web pública lleva al login; contraseña incorrecta y email inexistente dan el **mismo** mensaje; el admin aterriza en el Panel, sin nada en localStorage ni sessionStorage, y la única cookie es la de refresco con `HttpOnly`, `Secure`, `SameSite=Strict` y `Path` acotado (invisible para `document.cookie`); recargar **mantiene** la sesión; cerrar sesión la revoca; una **cookie robada y reutilizada** tumba la sesión |
| `registro.spec.ts` | Alguien nuevo se registra, entra sin empresa y se une con el código; registrarse con un email existente no revela nada ni le quita la cuenta; una cuenta pendiente puede cerrar sesión |
| `gestor.spec.ts` | La gestora ve las incidencias de su empresa (con quién las reportó) y no las de otra; regenera el código y el anterior deja de valer; desactiva a una trabajadora, que ya no entra, y la reactiva |
| `incidencias.spec.ts` | Un trabajador reporta una incidencia y la ve; no ve el centro de seguridad; otro cliente no la ve en su lista y la **API se la niega (404) aunque conozca el id**, también al editarla; el admin la ve con su cliente |
| `administracion.spec.ts` | Alta de un cliente (código sugerido) y de un usuario suyo con contraseña generada, que entra; al **dar de baja el cliente**, su contraseña sigue siendo buena pero la API le cierra la puerta; la auditoría registra las entradas |
| `sensores.spec.ts` | Un evento de un sensor aparece **en vivo** en el Panel con su cliente (SSE a través del proxy); la ingesta rechaza un token incorrecto; una ruta con HTML malicioso se muestra **como texto** (XSS almacenado); la pantalla de Sensores marca el señuelo como «Enviando» |

Si algo falla, cada servicio deja su salida en `frontend/test-results/<servicio>.log` y
Playwright guarda la traza y una captura de la prueba fallida.

### Integración continua (GitHub Actions)

En cada push y pull request:

1. **Backend**: `ruff` (lint y formato) → `bandit` → `pip-audit --strict` → `pytest` contra un
   PostgreSQL 17 real → lint y tests del señuelo.
2. **Imagen de la API**: build y comprobación de que no corre como root.
3. **Frontend**: `npm audit` de las dependencias de runtime (nivel alto) → tests unitarios
   (Vitest) → build → imagen sin root.
4. **Imagen del señuelo**: build y comprobación de que no corre como root.
5. **E2E**: la suite de Playwright completa. Si falla, sube el informe, las trazas y los logs de
   cada servicio como artefacto.
6. **Deploy** (solo en push a `main`, y solo si los cinco anteriores pasan): llama a la API de
   Dokploy para desplegar el compose. El auto-deploy de Dokploy está **desactivado**: si no, cada
   push llegaría a producción aunque la CI fallara, y los controles serían un aviso, no una
   barrera.

---

## 16. Datos de demostración

`python -m app.cli sembrar-demo` es idempotente. Crea:

| Cliente | Sector | Usuarios de demo |
|---|---|---|
| Transportes Ibarra | Logística | `p.lopez`, `c.navarro` |
| Clínica Solana | Sanidad | `j.moreno` |
| Hotel Mirador | Hostelería | `becario` |
| Kaelum (personal propio) | — | `a.ruiz`, `m.soto`, `l.vega` (analistas; `l.vega` desactivado) |

Además, **12 incidencias** realistas (phishing a RR. HH., VPN desde un país no habitual, hoja con
datos de clientes expuesta…), cada una con su historial de estados, notas y auditoría.

- Las cuentas de demo tienen contraseñas aleatorias que no se guardan en ningún sitio: nadie puede
  entrar con ellas. Sirven para que haya reportantes, analistas e historial.
- El dominio de los emails (`demo-incidentes.es`) es ficticio: nunca se envía nada.
- Sobre una base de datos sembrada antes de existir los clientes, solo completa lo que falta.

---

## 17. Decisiones y contrapartidas

| Decisión | Se gana | Se pierde o se asume |
|---|---|---|
| **Autenticación propia en lugar de Firebase** | Control total de la rotación, la revocación y la auditoría de intentos fallidos; sin dependencia externa | Guardamos los hashes de las contraseñas; sin recuperación de cuenta por email; la custodia de `JWT_SECRETO` es nuestra |
| **HS256 (clave simétrica)** | Simple: un único servicio firma y verifica | Quien verifica también podría firmar. Con varios servicios verificando tokens habría que pasar a RS256/EdDSA |
| **Versión de sesión en el token** | Revocación inmediata sin lista negra de tokens ni consultas extra | Una columna más; revoca todos los dispositivos a la vez |
| **Refresh en cookie `HttpOnly`, access en memoria** | Un XSS no puede robar ninguno de los dos; la sesión sobrevive a una recarga | La cookie exige mismo sitio (`SameSite=Strict`) y un `Path` bien configurado tras el proxy |
| **Rol y empresa en nuestra BD, no en el token** | Cambios inmediatos sin revocar nada | Una consulta a la BD por petición |
| **Señuelo de solo registro** | Tráfico real sin riesgo: no hay nada que explotar | Solo ve lo que llega por HTTP a su dominio |
| **Rechazar lotes con empresa desconocida** | Un sensor mal configurado se nota al momento | Ese lote se pierde |
| **Un único worker** | Simplicidad | El límite de peticiones vive en memoria; para escalar habría que pasarlo a Redis |
| **Precios solo como texto** | La web cuenta la historia completa | No hay facturación |

---

## 18. Referencia rápida

### Endpoints

| Método | Ruta | Quién |
|---|---|---|
| `GET` | `/salud` | Público |
| `POST` | `/auth/web/login`, `/auth/web/refrescar`, `/auth/web/logout` | Público (navegador: refresco en cookie). Login 5/min |
| `POST` | `/auth/login`, `/auth/refrescar`, `/auth/logout` | Público (Postman y scripts: refresco en el cuerpo). Login 5/min |
| `POST` | `/auth/web/mfa`, `/auth/mfa` | Público (desafío + código). 5/min |
| `GET` | `/auth/oauth/proveedores` | Público |
| `GET` | `/auth/oauth/{proveedor}/inicio`, `/callback` | Público (navegación del navegador) |
| `GET` | `/usuarios/yo` | Autenticado |
| `PATCH` | `/usuarios/yo/contrasena` | Autenticado, 5/min |
| `POST` | `/usuarios/yo/mfa/iniciar`, `/activar`, `/codigos`, `/desactivar` | Autenticado, 5/min |
| `POST` | `/usuarios/yo/identidades/{proveedor}`, `/{proveedor}/desvincular` | Autenticado, 5/min (prueba fresca: contraseña, código MFA o login reciente) |
| `DELETE` | `/usuarios/{id}/mfa` | Admin |
| `GET`, `POST` | `/usuarios` | Admin |
| `PATCH` | `/usuarios/{id}/rol`, `/activo`, `/contrasena` | Admin |
| `GET`, `POST` | `/empresas` | Admin |
| `GET`, `PATCH` | `/empresas/{id}` | Admin |
| `GET`, `POST` | `/incidentes` | Autenticado (lo visible para cada rol) |
| `GET`, `PATCH`, `DELETE` | `/incidentes/{id}` | Según rol |
| `PATCH` | `/incidentes/{id}/estado`, `/asignar`, `/notas` | Según rol |
| `POST` | `/eventos` | Sensores (`X-Ingesta-Token`) |
| `GET` | `/eventos`, `/eventos/resumen`, `/eventos/sensores`, `/eventos/stream` | Admin |
| `PATCH` | `/eventos/{id}` | Admin (triaje) |
| `POST` | `/eventos/{id}/incidente` | Admin |
| `GET` | `/eventos/por-incidente/{id}` | Admin |
| `GET` | `/auditoria` | Admin |

Los listados admiten `limite` y `desplazamiento`. Eventos, resumen, incidencias y usuarios
admiten además `empresa_id`.

### Comandos

```bash
cd backend && uv run pytest --cov                 # tests de la API
cd backend && uv run pytest ../senuelo            # tests del clasificador
cd backend && uv run ruff check . ../senuelo && uv run bandit -c pyproject.toml -r app
cd frontend && npx ng test --watch=false          # unitarias del front
cd frontend && npx playwright test                # E2E
cd frontend && npx ng build                       # compilar el front
docker compose exec api python -m app.cli crear-admin <email>
docker compose exec api python -m app.cli sembrar-demo
```

### Documentos relacionados

| Documento | Contenido |
|---|---|
| [`README.md`](../README.md) | Visión general, estructura del repositorio, arranque, testing y CI/CD |
| [`backend/README.md`](../backend/README.md) | API: variables de entorno, endpoints, migraciones, CLI y backups |
| [`frontend/README.md`](../frontend/README.md) | SPA: estructura, decisiones de seguridad, tests unitarios y E2E |
| [`senuelo/README.md`](../senuelo/README.md) | Sensores en detalle |
| [`postman/README.md`](../postman/README.md) | Colección de la API |
