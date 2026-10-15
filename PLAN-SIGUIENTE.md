# Plan siguiente — Umbral (Kaelum Security)

Decidido el 2026-10-14. Este fichero es la fuente de verdad para retomar en cualquier máquina
(Engram no se sincroniza entre ordenadores).

## Estado de partida

- En producción y verificado: web `…d84d64-51-77-145-58.sslip.io` (front + `/api`), señuelo
  `…bcaf63-51-77-145-58.sslip.io`, `INGESTA_TOKEN` configurado en Dokploy.
- Último commit: `0ecf7f4` (resumen periódico del señuelo). **Falta redeploy** para que salga.
- Autenticación actual: **propia** (PyJWT HS256 + argon2 + refresco con hash en
  `tokens_refresco` + cookie HttpOnly en `/auth/web/*`). No hay nada de Firebase todavía.

## Orden acordado (2026-10-14)

Tanda 1 → Tanda 2 → Tanda 0 (Firebase al final). La Tanda 1 no depende de Firebase y así
producción nunca queda sin login a medias. Al migrar, `POST /usuarios` pasa a crear la cuenta
con el Admin SDK manteniendo las reglas de empresa.

**Tanda 1: hecha** (migración `0004`). Pendiente al desplegar: `python -m app.cli sembrar-demo`
en el contenedor de la API **antes** de que arranquen señuelo y generador, o la ingesta
rechaza sus lotes con 422 (empresa desconocida). Variables nuevas, con valor por defecto:
`EMPRESA_SENUELO` (hotel-mirador) y `EMPRESAS_GENERADOR` (los tres clientes de demo).

**Tanda 2: hecha.** Menú nuevo, pantallas Clientes y Sensores (`GET /eventos/sensores`),
selector de cliente en Panel, Eventos, Incidencias y Usuarios, entrada según rol y vocabulario
«incidencia». Además: landing pública en `/` y marca Kaelum Security en login y pestañas.

**Tanda 0: hecha y verificada en producción (2026-10-15).** Firebase Auth con
`inMemoryPersistence` (comprobado: sin Local/Session Storage, sin IndexedDB, sin cookies; recargar
pide login). Admin creado con `crear-admin`. Las cuentas reales anteriores se migran cuando un admin
les restablece la contraseña. Pendiente menor: borrar `JWT_SECRETO` del Environment de Dokploy.

Descartado por ahora: precios y facturación (no aportan a PPS). Opcional: un campo `plan`
descriptivo en la empresa.

## Tanda 0 — Migrar la autenticación a Firebase

**Antes de empezar, el alumno aporta** (nunca en el chat ni en el repo):
- Proyecto de Firebase con Authentication → proveedor *Email/Password* activado.
- *Web API key* y config del SDK web (no son secretos, van en el front).
- *Service account* JSON del Admin SDK → variable de entorno en Dokploy
  (`FIREBASE_CREDENCIALES`, el JSON entero o en base64). **Secreto.**

**Backend**
1. Dependencia `firebase-admin`. Verificar el ID token en `usuario_actual`
   (`auth.verify_id_token(token, check_revoked=True)`), no a mano con PyJWT.
2. `usuarios.firebase_uid` (único). El **rol y la empresa siguen en nuestra BD**: nunca se
   fían de *custom claims* que no hayamos puesto nosotros.
3. Alta de cuentas (`POST /usuarios`, admin): crea el usuario con el Admin SDK y guarda el
   `uid`. Restablecer contraseña y desactivar → Admin SDK + `revoke_refresh_tokens(uid)`.
4. Retirar: `/auth/login`, `/auth/refrescar`, `/auth/logout`, `/auth/web/*`, tabla
   `tokens_refresco`, `hash_contrasena`, argon2, `COOKIE_REFRESCO_RUTA`. Migración Alembic.
5. `crear-admin` del CLI: crea/promueve vía Admin SDK.
6. Tests: mockear `verify_id_token` (sin red).

**Frontend**
1. SDK de Firebase empaquetado (sin CDN). `signInWithEmailAndPassword` → `getIdToken()` →
   `Authorization: Bearer`. El SDK renueva solo el token.
2. **Persistencia `inMemoryPersistence`** para mantener la política «token solo en memoria»
   (por defecto Firebase lo guarda en IndexedDB). Coste: recargar la página pide login otra vez;
   alternativa `browserSessionPersistence` (muere al cerrar la pestaña). Decidir con el alumno.
3. CSP: `connect-src` a `identitytoolkit.googleapis.com` y `securetoken.googleapis.com`.
4. El interceptor deja de refrescar con cookie: pide `getIdToken()` al SDK.

**Contrapartidas a explicar en PPS**
- Se gana: gestión de credenciales, recuperación de contraseña y protección anti fuerza bruta
  de Google.
- Se pierde: el `login_fallido` en nuestra auditoría (lo ve Firebase, no nosotros) y el
  control propio de la rotación y reutilización de refrescos.
- Postman: el login pasa a la API REST de Firebase (`accounts:signInWithPassword`).

## Tanda 1 — Backend multiempresa (MSSP)

- Tabla `empresas` (nombre, sector, activa) + CRUD admin. Clientes de demo: *Transportes Ibarra*,
  *Clínica Solana*, *Hotel Mirador*.
- `empresa_id` en usuarios (null = personal de Kaelum: admin/analista), incidencias y eventos.
- **Aislamiento en el servidor:** un usuario de cliente solo ve lo de su empresa; lo ajeno da 404.
- El señuelo declara su empresa (`EMPRESA` en el entorno); el generador reparte entre clientes.
- Filtro `empresa` en eventos, resumen e incidencias para el personal de Kaelum.
- **Tests de aislamiento:** usuario de Ibarra intenta leer, editar y listar cosas de Solana → todo falla.

## Tanda 2 — Frontend

Menú acordado:

```
UMBRAL · Kaelum Security
INCIDENCIAS            (todos)   Incidencias · Reportar incidencia
CENTRO DE SEGURIDAD    (admin)   Panel · Eventos · Sensores
ADMINISTRACIÓN         (admin)   Clientes · Usuarios · Auditoría
(abajo)                          usuario · Mi cuenta · Cerrar sesión
```

- Al entrar: el admin aterriza en Panel; el trabajador en Incidencias.
- Vocabulario único: «incidencia» = ticket de una persona; «evento» = lo que detecta un sensor.
- Pantalla **Sensores**: estado del señuelo y del generador por cliente (último evento, total).
- Selector de cliente en Panel y Eventos.
