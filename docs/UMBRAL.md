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
5. [Autenticación con Firebase](#5-autenticación-con-firebase)
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

Email y contraseña. No hay registro público: las cuentas las crea un administrador. Tras entrar,
el admin aterriza en el **Panel** y el resto en sus **Incidencias**.

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
         │          └─────┘ └──┬─────┘ ◄──────── │generador │  (eventos de demo)
         │        estáticos    │                 └──────────┘
         │                     ▼
         │                ┌─────────┐   ┌────────┐
         │                │Postgres │◄──│ backup │  pg_dump diario
         │                └─────────┘   └────────┘
         │
         └──────► Firebase Authentication (Google): login y emisión de ID tokens
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

**Capas del backend** (`app/`):

```
routers/        HTTP y validación de entrada. Sin lógica
servicios/      Reglas de negocio y permisos, en un solo sitio, y auditoría
repositorios.py Acceso a datos (SQLAlchemy). Sin reglas
modelos.py      Tablas
esquemas.py     Entrada y salida (Pydantic), siempre separadas
identidad.py    Único módulo que habla con Firebase
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
| Alembic | ≥ 1.20 | Migraciones (`0001` a `0005`) |
| Pydantic + pydantic-settings | ≥ 2.13 | Validación y configuración por entorno |
| firebase-admin | ≥ 7.7 | Verificar ID tokens y gestionar cuentas |
| slowapi | ≥ 0.1.10 | Límite de peticiones |
| uvicorn | ≥ 0.54 | Servidor ASGI |
| uv | — | Gestión de dependencias con lockfile |

### Frontend

| Tecnología | Versión | Para qué |
|---|---|---|
| Angular | 21 | SPA con componentes *standalone*, señales y `OnPush` |
| Angular CDK | 21 | Overlays de los desplegables |
| @firebase/app + @firebase/auth | 0.16 / 1.13 | Login. **Solo** Auth: no el paquete `firebase` completo |
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
| Firebase Authentication | Proveedor de identidad (proyecto `kaelum-837f9`) |
| GitHub Actions | Integración continua |

### Sensores

Python 3.12 con **solo la librería estándar** (`http.server`, `urllib`, `re`): ninguna
dependencia de terceros que mantener ni auditar.

---

## 5. Autenticación con Firebase

### Flujo de entrada

```
navegador                      Firebase                          API de Umbral
   │ email + contraseña  ───────► │                                   │
   │ ◄─────────── ID token (JWT firmado por Google, 1 h)              │
   │ POST /auth/sesion  (Authorization: Bearer <token>) ─────────────►│
   │                                │   verifica firma, caducidad y   │
   │                                │   revocación (check_revoked)    │
   │                                │   busca el uid en SU base       │
   │                                │   de datos: activo, rol, empresa│
   │ ◄──────────────────────────────────────── 204 + «login» auditado │
   │ GET /usuarios/yo  ───────────────────────────────────────────────►│
```

- **Firebase dice quién eres**: comprueba la contraseña y firma el token.
- **Nuestra base de datos dice qué puedes hacer**: rol, empresa y si la cuenta está activa se
  leen en **cada** petición. El token no lleva el rol, así que un cambio de rol es inmediato.
- **Un `uid` desconocido no entra.** La API key de Firebase es pública: cualquiera podría crearse
  una cuenta de Firebase por su cuenta. Sin fila en nuestra tabla `usuarios`, recibe un 401.

### Persistencia solo en memoria

El SDK se inicia con `inMemoryPersistence`. Por defecto, Firebase guarda la sesión en IndexedDB.

| Se comprobó en producción | Resultado |
|---|---|
| Local Storage y Session Storage | Vacíos |
| IndexedDB (`firebaseLocalStorageDb`) | No existe |
| Cookies | Ninguna de sesión |
| Recargar la página | Pide entrar otra vez |

Un XSS no encuentra un token guardado que robar. Coste asumido: cada recarga pide login.

El SDK renueva el ID token solo, cada hora, contra `securetoken.googleapis.com`, mientras la
pestaña siga abierta. Ante un 401, el interceptor pide un token nuevo, repite la petición una vez
y, si vuelve a fallar, devuelve al login.

### Operaciones de cuenta

| Operación | Qué pasa |
|---|---|
| Alta (admin) | La cuenta se crea en Firebase con el Admin SDK y su `uid` se guarda en nuestra BD |
| Restablecer contraseña (admin) | Contraseña nueva en Firebase y **revocación** de sus sesiones. Si la cuenta es anterior a la migración (sin `uid`), es este paso el que la crea en Firebase |
| Cambiar la propia contraseña | La API comprueba la actual contra Firebase, cambia la contraseña y revoca todas las sesiones; el front vuelve a entrar con la nueva |
| Desactivar (admin) | `activo = false` en nuestra BD (efecto inmediato) y cuenta deshabilitada y revocada en Firebase |
| Primer admin | `python -m app.cli crear-admin <email>`, con la contraseña pedida por consola |

### Configuración

| Variable | Secreta | Dónde vive |
|---|---|---|
| `FIREBASE_CREDENCIALES` | **Sí**: base64 del JSON de la cuenta de servicio | Solo en el servicio `api` |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID` | No | La API se las da al front en `GET /config/cliente` |

En producción, la API **no arranca** si faltan las credenciales, la API key o el proyecto.

---

## 6. Roles y permisos

| Acción | usuario | analista | admin |
|---|---|---|---|
| Reportar incidencia | ✅ | ✅ | ✅ |
| Ver incidencias | las suyas | las asignadas y las suyas | todas |
| Editar título, descripción y categoría | las suyas, solo en `abierto` | ❌ | ✅ |
| Notas internas (ver y escribir) | ❌ | las asignadas | ✅ |
| Cambiar estado | ❌ | las asignadas | ✅ |
| Asignar analista, reabrir y borrar | ❌ | ❌ | ✅ |
| Panel, eventos, sensores y triaje | ❌ | ❌ | ✅ |
| Clientes, usuarios y auditoría | ❌ | ❌ | ✅ |

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
- `empresa_id = NULL` en un usuario significa **personal de Kaelum**.

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
| Contraseñas | **No las guarda Umbral**: viven en Firebase | — |
| Incidencias (texto, severidad, notas) | Usuarios y analistas | Indefinida; el borrado es lógico |
| Eventos: IP de origen, método, ruta, user-agent, servicio, cliente y fecha | Sensores | **30 días** (`EVENTOS_RETENCION_DIAS`), salvo los enlazados a una incidencia, que son evidencia |
| Auditoría: quién, qué acción, sobre qué recurso, IP y fecha | La propia API | Indefinida |
| Copias de seguridad | `pg_dump` diario | 7 días |

- La purga de eventos se reparte en el tiempo: se ejecuta, de media, una de cada 200 ingestas, sin
  necesidad de cron.
- La IP de quien sondea el señuelo es un dato personal (RGPD). Se guarda con una finalidad de
  seguridad y con un plazo acotado.
- Ningún dato se envía a terceros, salvo el login a Firebase, que es el proveedor de identidad.

---

## 11. Auditoría

Cada acción sensible deja un registro con usuario, acción, recurso, IP y fecha.

| Grupo | Acciones |
|---|---|
| Sesión | `login`, `logout` |
| Cuentas | `crear_usuario`, `restablecer_contrasena`, `cambio_contrasena`, `cambio_contrasena_fallido`, `cambio_rol`, `desactivar_usuario`, `reactivar_usuario`, `crear_admin_cli` |
| Clientes | `crear_empresa`, `editar_empresa` |
| Incidencias | `crear_incidente`, `editar_incidente`, `cambio_estado`, `asignar_incidente`, `editar_notas`, `borrar_incidente` |
| Eventos | `triaje_evento` |

Anteriores a la migración a Firebase (siguen en el historial): `login_fallido`,
`reutilizacion_token`, `registro`.

La IP real llega por `X-Forwarded-For` de Traefik. Uvicorn solo se fía de esa cabecera porque la
API no publica ningún puerto: no hay otro camino que el proxy.

---

## 12. Seguridad aplicada, capa a capa

### Identidad y acceso

- Firebase Authentication, con verificación del token y de su revocación en cada petición.
- Rol, empresa y estado de la cuenta leídos de la BD, nunca del token.
- Sin registro público; las altas, solo por un admin.
- Contraseñas de 12 caracteres como mínimo. El generador del alta usa `crypto.getRandomValues`.
- Cambiar la propia contraseña exige la actual y está limitado a **5 intentos por minuto**.

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
  **Trusted Types**, y `connect-src` abierto solo al propio dominio y a los dos de Firebase.
- Estilos dinámicos aplicados por el CSSOM, no con atributos `style`.
- Token solo en memoria. Fuentes servidas desde el propio dominio.

### Contenedores y red

| Medida | Dónde |
|---|---|
| Imágenes slim multi-stage, sin herramientas de build | `Dockerfile` |
| Usuario sin privilegios (uid 10001) | `Dockerfile` |
| Sistema de ficheros de solo lectura, `/tmp` en memoria | `docker-compose.yml` |
| `cap_drop: ALL` y `no-new-privileges` | `docker-compose.yml` |
| PostgreSQL sin puerto publicado | `docker-compose.yml` |
| Sin cabecera `Server` (`--no-server-header`) | `Dockerfile` |
| La credencial de Firebase solo llega al servicio `api` | `docker-compose.yml` |

### Secretos

- Nunca en el repositorio: se configuran en Dokploy.
- `.gitignore` cubre `.env` y los JSON de cuentas de servicio (`*-adminsdk-*.json`).
- La credencial de Firebase viaja en base64 para que los saltos de línea de la clave no rompan
  la variable.

---

## 13. OWASP Top 10

Correspondencia entre las categorías del **OWASP Top 10:2025** y lo que hace Umbral. Conviene
comprobar la versión vigente en <https://owasp.org/Top10/>.

| Categoría | Riesgo | Cómo se mitiga en Umbral | Dónde mirar |
|---|---|---|---|
| **A01 Broken Access Control** | Ver o tocar lo que no es tuyo (IDOR, escalada) | Permisos centralizados en los servicios; 404 para lo ajeno; aislamiento por empresa **antes** del rol; filtro de empresa forzado para clientes; rol leído de la BD en cada petición; esquemas de entrada sin `rol`, `estado` ni `reportante_id` | `app/servicios/incidentes.py`, `tests/test_empresas.py` |
| **A02 Security Misconfiguration** | Valores por defecto inseguros, información de más | `/docs` desactivado en producción; errores sin trazas; CSP, HSTS, `nosniff` y `DENY`; CORS con lista blanca; sin cabecera `Server`; contenedores de solo lectura y sin capabilities; la API no arranca sin Firebase | `app/main.py`, `nginx/cabeceras-seguridad.conf`, `docker-compose.yml` |
| **A03 Software Supply Chain Failures** | Dependencias vulnerables o comprometidas | Lockfiles (`uv.lock`, `package-lock.json`); `pip-audit --strict` y `npm audit` en CI; sensores sin dependencias; solo `@firebase/auth` (el paquete completo traía 4 vulnerabilidades altas por gRPC); imágenes base fijadas | `.github/workflows/ci.yml` |
| **A04 Cryptographic Failures** | Secretos o datos sensibles mal protegidos | Sin contraseñas propias (las guarda Firebase); TLS en todo; ID tokens firmados por Google; token de ingesta comparado en tiempo constante; secretos fuera del repo | `app/identidad.py`, `app/routers/eventos.py` |
| **A05 Injection** | SQL, XSS, inyección en logs | ORM con parámetros enlazados; `LIKE` escapado; Angular escapa por defecto y la CSP con Trusted Types bloquea sumideros de DOM; los caracteres de control se quitan de lo que llega de internet | `app/repositorios.py`, `app/esquemas.py` |
| **A06 Insecure Design** | Fallos de diseño, no de código | Sin registro público; borrado lógico (evidencia); reporte congelado al pasar a análisis; máquina de estados con 409; el señuelo no es explotable por diseño | `app/servicios/`, `senuelo/` |
| **A07 Authentication Failures** | Credenciales débiles, sesiones robadas | Firebase con protección contra fuerza bruta; mínimo 12 caracteres; `check_revoked`; revocación al cambiar o restablecer la contraseña y al desactivar; token solo en memoria; cambiar la contraseña exige la actual (5/min) | `app/servicios/usuarios.py`, `core/sesion.ts` |
| **A08 Software or Data Integrity Failures** | Datos o código manipulados | La CI bloquea el merge si falla una comprobación; migraciones versionadas y probadas; los campos de un evento no se editan nunca, solo el triaje | `tests/test_migraciones.py` |
| **A09 Logging & Alerting Failures** | No enterarse de un ataque | Auditoría de todas las acciones sensibles con IP real; el panel resalta alertas; el señuelo informa cada 5 minutos de entregados y perdidos; los intentos fallidos de login los registra Firebase | `app/servicios/auditoria.py` |
| **A10 Mishandling of Exceptional Conditions** | Errores que dejan el sistema en un estado inseguro | Manejador global que responde 500 genérico y registra la traza; fallos de verificación del token resueltos como 401 (se deniega, no se concede); los lotes de ingesta inválidos se rechazan enteros; un volcado de backup fallido no deja ficheros a medias | `app/main.py`, `app/identidad.py` |

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
| `FIREBASE_CREDENCIALES` | Obligatoria y **secreta** |
| `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_PROJECT_ID` | Obligatorias (públicas) |
| `INGESTA_TOKEN` | Mínimo 32 caracteres. Vacía, la ingesta queda desactivada |
| `CORS_ORIGENES` | Opcional |
| `EMPRESA_SENUELO` | Por defecto `hotel-mirador` |
| `EMPRESAS_GENERADOR` | Por defecto, los tres clientes de demo |

### Puesta en marcha desde cero

1. Proyecto de Firebase con Email/Password activado y el dominio web en *Dominios autorizados*.
2. Variables en Dokploy y despliegue del compose. Las migraciones se aplican al arrancar la API.
3. En el contenedor `api`:
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
| **Unitarias del backend** | pytest | Clasificador del señuelo | 12 |
| **Integración de la API** | pytest + httpx + BD real | Cada endpoint por HTTP, con permisos y efectos en la BD | 130 |
| **Unitarias del front** | Vitest (`ng test`) | Interceptor, guardas, servicio de clientes, errores, utilidades | 52 |
| **E2E** | Playwright + emulador de Firebase Auth | Flujos completos en un navegador real contra la pila entera | 16 |
| **Seguridad estática** | ruff (reglas `S`), bandit | Código de la API | — |
| **Dependencias** | pip-audit, npm audit | Backend y front | — |

```bash
uv run pytest                     # integración de la API
uv run pytest senuelo/            # unitarias del clasificador
cd frontend/web
npx ng test --watch=false         # unitarias del front
npx playwright test               # E2E (levanta todo solo)
```

### Tests de integración de la API

Cada test levanta la aplicación real en memoria y le habla por HTTP con `httpx`. En local la base
de datos es SQLite y en la CI un **PostgreSQL 17 real**. Se prueba el comportamiento que vería un
cliente (códigos, cuerpos y efectos en la BD), no funciones sueltas.

| Fichero | Qué cubre |
|---|---|
| `test_identidad.py` | Sin token, token inventado, `uid` desconocido (registro por libre en Firebase), token revocado, rol desde la BD, auditoría de entrada y salida, config pública sin secretos, producción sin Firebase no arranca |
| `test_empresas.py` | CRUD de clientes, reglas de miembros, **aislamiento** (leer, editar, cambiar estado, notas, listar y filtro forzado), defensa en profundidad con un reportante falseado, baja de un cliente, ingesta, resumen, sensores e incidencia desde evento por cliente |
| `test_incidentes.py` | Permisos por rol, IDOR, transiciones y 409, notas internas ocultas al reportante, borrado lógico, auditoría |
| `test_usuarios.py` | Filtros (incluido `LIKE` con comodines), altas, emails duplicados (también en Firebase), cambio de contraseña con revocación, límite de 5/min, restablecimiento, migración de cuentas antiguas, activar y desactivar |
| `test_eventos.py` | Token de ingesta (sin token, incorrecto, un JWT de admin no vale), limpieza y truncado, IP inválida, tamaño de lote, filtros, resumen y tramos, triaje, SSE solo para admin, incidencia desde evento |
| `test_migraciones.py` | Las migraciones coinciden con los modelos; el downgrade deja la BD vacía |
| `test_plataforma.py` | Salud, cabeceras de seguridad, CORS permitido y rechazado, error 422, prefijo `/api` |
| `test_demo.py` | Semilla idempotente, reparto por clientes, completado de una BD sembrada antes |

**Sin red.** Firebase se sustituye por un proveedor falso en memoria (`IdentidadFalsa` en
`tests/conftest.py`). Emite tokens `falso:<uid>:<generación>`: revocar sube la generación e
invalida los anteriores, igual que `check_revoked`. El helper `cabeceras()` inicia sesión como lo
hace el front: credenciales contra el falso y `POST /auth/sesion`.

### Tests unitarios

**Backend:** `senuelo/test_clasificador.py` prueba cada regla del WAF con ejemplos reales
(recorrido de rutas, inyección, ficheros sensibles, escáneres) y casos que no deben coincidir. El
resto de la lógica (máquina de estados, permisos, aislamiento) se prueba a través de la API, que
es donde importa: un permiso bien escrito pero mal enganchado al router no protege nada.

**Front** (`frontend/web/src/**/*.spec.ts`, Vitest con jsdom):

| Fichero | Qué cubre |
|---|---|
| `core/interceptor.spec.ts` | Añade el Bearer; no lo envía a rutas públicas; ante un 401 pide un token nuevo y repite una vez; si vuelve a fallar, cierra la sesión y va al login; en `/api/auth/*` no reintenta |
| `core/guardas.spec.ts` | Sesión obligatoria, solo invitados, solo admin y landing solo sin sesión |
| `core/clientes.spec.ts` | Caché de clientes (una sola carga, reintento si falla), nombres, opciones de filtro y de alta (sin clientes de baja) |
| `core/errores.spec.ts` | Mensajes por código, sin trazas de un 500; traducción de errores de Firebase (una cuenta deshabilitada se ve igual que una contraseña mala) |
| `paginas/clientes.spec.ts` | El código sugerido de un cliente siempre lo acepta la API |

### E2E (Playwright)

`npx playwright test` levanta solo, sin Docker y sin tocar nada real
(`frontend/web/e2e/entorno.mjs`):

1. Compila el front **para producción**.
2. Arranca el **emulador oficial de Firebase Auth**, con un proyecto `demo-` que no necesita cuenta
   de Google.
3. Crea una base de datos nueva, aplica las migraciones y siembra dos clientes, un admin y un
   trabajador de cada cliente (`tests/e2e_semilla.py`, que se niega a correr sin emulador).
4. Arranca la **API real** apuntando al emulador.
5. Sirve el build con **las mismas cabeceras que nginx**, leídas de
   `nginx/cabeceras-seguridad.conf` (CSP con nonce y Trusted Types incluidos), y reenvía `/api` a
   la API como hace Traefik. La única diferencia es que `connect-src` permite el emulador local.

Cada prueba **falla si el navegador registra una violación de la CSP o de Trusted Types, un error
de JavaScript o un diálogo inesperado** (fixture `vigilancia` en `e2e/ayudas.ts`). Así, todos los
flujos verifican de paso que la política de seguridad de producción no rompe la app.

| Fichero | Escenarios |
|---|---|
| `acceso.spec.ts` | La web pública lleva al login; contraseña incorrecta y email inexistente dan el **mismo** mensaje; el admin aterriza en el Panel y **no queda nada** en localStorage, sessionStorage, IndexedDB ni cookies; recargar pide entrar otra vez; cerrar sesión vuelve a la web pública; una cuenta creada por libre en Firebase **no entra** |
| `incidencias.spec.ts` | Un trabajador reporta una incidencia y la ve; no ve el centro de seguridad; otro cliente no la ve en su lista y la **API se la niega (404) aunque conozca el id**, también al editarla; el admin la ve con su cliente |
| `administracion.spec.ts` | Alta de un cliente (código sugerido) y de un usuario suyo con contraseña generada, que entra; al **dar de baja el cliente**, Firebase le deja iniciar sesión pero Umbral le cierra la puerta; la auditoría registra las entradas |
| `sensores.spec.ts` | Un evento de un sensor aparece **en vivo** en el Panel con su cliente (SSE a través del proxy); la ingesta rechaza un token incorrecto; una ruta con HTML malicioso se muestra **como texto** (XSS almacenado); la pantalla de Sensores marca el señuelo como «Enviando» |

El modo emulador **está prohibido en producción**: con él, el Admin SDK aceptaría tokens sin firmar.
La configuración se niega a arrancar si `ENTORNO=produccion` y `FIREBASE_AUTH_EMULATOR_HOST` está
definida (cubierto por `test_identidad.py`).

Si algo falla, cada servicio deja su salida en `frontend/web/test-results/<servicio>.log` y
Playwright guarda la traza y una captura de la prueba fallida.

### Integración continua (GitHub Actions)

En cada push y pull request:

1. **Backend**: `ruff` (lint y formato) → `bandit` → `pip-audit --strict` → `pytest` contra un
   PostgreSQL 17 real → tests del señuelo.
2. **Imagen de la API**: build y comprobación de que no corre como root.
3. **Frontend**: `npm audit` de las dependencias de runtime (nivel alto) → tests unitarios
   (Vitest) → build → imagen sin root.
4. **Imagen del señuelo**: build y comprobación de que no corre como root.
5. **E2E**: la suite de Playwright completa contra el emulador. Si falla, sube el informe, las
   trazas y los logs de cada servicio como artefacto.

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

- Las cuentas de demo **no existen en Firebase**: nadie puede entrar con ellas. Sirven para que haya
  reportantes, analistas e historial.
- El dominio de los emails (`demo-incidentes.es`) es ficticio: nunca se envía nada.
- Sobre una base de datos sembrada antes de existir los clientes, solo completa lo que falta.

---

## 17. Decisiones y contrapartidas

| Decisión | Se gana | Se pierde o se asume |
|---|---|---|
| **Firebase en lugar de autenticación propia** | No guardar contraseñas, recuperación de cuentas, protección contra fuerza bruta de Google | Los intentos fallidos no llegan a nuestra auditoría; dependencia de un proveedor externo; sin control propio de la rotación de tokens |
| **Persistencia en memoria** | Ningún token persistente al alcance de un XSS | Recargar la página pide login |
| **Rol y empresa en nuestra BD, no en *custom claims*** | Cambios inmediatos; nunca nos fiamos de datos que no pusimos nosotros | Una consulta a la BD por petición |
| **Señuelo de solo registro** | Tráfico real sin riesgo: no hay nada que explotar | Solo ve lo que llega por HTTP a su dominio |
| **Rechazar lotes con empresa desconocida** | Un sensor mal configurado se nota al momento | Ese lote se pierde |
| **`@firebase/auth` en lugar del paquete `firebase` completo** | Sin Firestore ni gRPC: 0 vulnerabilidades altas y menos superficie | — |
| **Config de Firebase servida por la API** | Nada compilado en la imagen; cambiarla no exige reconstruir | Una petición más al arrancar |
| **Un único worker** | Simplicidad | El límite de peticiones vive en memoria; para escalar habría que pasarlo a Redis |
| **Precios solo como texto** | La web cuenta la historia completa | No hay facturación |

---

## 18. Referencia rápida

### Endpoints

| Método | Ruta | Quién |
|---|---|---|
| `GET` | `/salud`, `/config/cliente` | Público |
| `POST` | `/auth/sesion`, `/auth/salida` | Autenticado (solo auditoría) |
| `GET` | `/usuarios/yo` | Autenticado |
| `PATCH` | `/usuarios/yo/contrasena` | Autenticado, 5/min |
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
uv run pytest                          # tests de la API
uv run pytest senuelo/                 # tests del clasificador
uv run ruff check . && uv run bandit -c pyproject.toml -r app
cd frontend/web && npx ng test --watch=false   # unitarias del front
cd frontend/web && npx playwright test         # E2E
cd frontend/web && npx ng build        # compilar el front
python -m app.cli crear-admin <email>  # en el contenedor api
python -m app.cli sembrar-demo         # en el contenedor api
```

### Documentos relacionados

| Documento | Contenido |
|---|---|
| `README.md` | Arranque, variables, endpoints y despliegue |
| `senuelo/README.md` | Sensores en detalle |
