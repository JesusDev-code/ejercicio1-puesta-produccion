# Colección de Postman

`api-incidentes.postman_collection.json` (126 peticiones, 191 comprobaciones) con los entornos
`local` y `produccion`. Usa las rutas `/auth/*` (el refresco viaja en el cuerpo) y el token de
acceso como Bearer.

## Qué recorre

- Los cuatro roles, con casos positivos y negativos, mass assignment e IDOR.
- Registro (mismo mensaje con un email existente), cuenta pendiente que no ve nada, unión con
  código (inventado → 422) y lo que el gestor puede y no puede tocar.
- Tokens manipulados: firma alterada, `alg=none`, inventados.
- Refresh tokens: rotación en cada uso, reutilización de uno ya rotado (revoca la familia y tumba
  al momento el access obtenido con la copia), logout.
- Revocación inmediata: tras cambiar o restablecer la contraseña, o tras una baja, el token de
  acceso anterior deja de valer aunque no haya caducado.
- Aislamiento entre clientes, también forzando el filtro, y baja de un cliente.
- Rate limit del login y del cambio de contraseña (la carpeta va la última).

El login admite 5 intentos por minuto e IP. La colección lleva la cuenta y, cuando haría falta un
sexto, **espera** a que se renueve la ventana: por eso tarda algo más de un minuto.

## Ejecutar en local

Contra una API con el limitador activo y un admin creado (desde la raíz del repo):

```bash
docker compose up -d
docker compose exec api python -m app.cli crear-admin admin@example.com
npx newman run postman/api-incidentes.postman_collection.json -e postman/local.postman_environment.json \
  --env-var admin_email=admin@example.com --env-var admin_contrasena=<la que elegiste>
```

La pila de los E2E (`frontend/e2e/entorno.mjs`) **no** sirve para la colección completa: arranca
la API con el rate limit desactivado.

## Ejecutar contra producción

Rellena `admin_email` y `admin_contrasena` como **valor actual** (así no se exportan) y ejecuta en
orden con el Runner. Cada ejecución crea usuarios, clientes e incidencias de prueba reales.

Usa dominios como `example.com`: el validador de email rechaza los de uso especial, como `.test`.
