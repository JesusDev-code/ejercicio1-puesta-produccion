# Diseño del frontend

Diseño aprobado el 2026-10-13. Lienzo interactivo (privado):
https://claude.ai/artifact/CjGtqu4KUTMK95o4imqzZx

`pantallas/` guarda el código fuente de cada pantalla (`.dc.html`) y la disposición del lienzo
(`canvas.json`). **No se abren directamente en el navegador**: dependen del runtime del lienzo
(`support.js`). Son la referencia exacta de marcado, estilos y lógica de cada pantalla para
pasarla al framework que se elija.

---

## Estilo: «Lemarchand»

Negro lacado, carmesí con resplandor, oro viejo, paneles de cristal esmerilado y una serif fina.
El toque retro lo ponen la monoespaciada y los glifos que aparecen y se desvanecen al azar.

**Regla de oro: sin líneas.** Nada de bordes en tarjetas, tablas o separadores. Las zonas se
separan por tono de fondo, cristal y espacio.

### Colores

| Token | Valor | Uso |
|---|---|---|
| `--fondo` | `#07050A` | Fondo de página |
| `--texto` | `#F1E6E0` | Texto principal (hueso) |
| `--texto-2` | `#CDBDC2` | Texto secundario, etiquetas de formulario |
| `--apagado` | `#A8939A` | Ayudas, subtítulos |
| `--tenue` | `#7D6A71` | Cabeceras de tabla, metadatos |
| `--sangre` | `#E01E3C` | Acento principal, estado activo del menú |
| `--sangre-claro` | `#FF5A6A` / `#FF7A88` | Texto de error, cursivas destacadas |
| `--oro` | `#D4AF6E` | Etiquetas mono, rutas `~/…` |
| `--oro-claro` | `#F0C987` | Botones secundarios, notas internas, enlaces |
| `--menta` | `#8FD3B8` | Éxito, «activo», resuelto |

**Severidad:** baja `#B8A5AB` · media `#F0C987` · alta `#FF9A5C` · crítica `#FF4D5E`
(siempre con punto luminoso: `box-shadow: 0 0 10px <color>`).

**Estado (píldora de texto sobre fondo translúcido del mismo color):**
abierto `#F1E6E0` · en análisis `#F0C987` · resuelto `#8FD3B8` · cerrado `#A8939A`.

### Fondos y superficies

```css
/* Página */
background:
  radial-gradient(1000px 520px at 70% -10%, rgba(196,18,47,.26), transparent 65%),
  radial-gradient(600px 400px at 0% 100%, rgba(212,175,110,.08), transparent 60%),
  #07050A;

/* Panel de cristal */
background: linear-gradient(170deg, rgba(255,255,255,.065), rgba(255,255,255,.018));
backdrop-filter: blur(20px);
box-shadow: inset 0 1px 0 rgba(255,255,255,.1), 0 30px 80px -40px rgba(0,0,0,.9);
border-radius: 22px;

/* Botón principal */
background: linear-gradient(180deg, #EC2A47, #A80D26);
box-shadow: inset 0 1px 0 rgba(255,255,255,.25), 0 0 0 1px rgba(255,90,110,.3),
            0 12px 32px -10px rgba(224,30,60,.75);
border-radius: 14px;

/* Input */
background: rgba(0,0,0,.35);
border: 1px solid rgba(255,255,255,.08);   /* única «línea» permitida, casi invisible */
border-radius: 14px;
/* :focus → border rgba(255,59,78,.7) + box-shadow 0 0 0 4px rgba(224,30,60,.18) */
```

Radios: inputs y botones 12–14 px · tarjetas 16–24 px · píldoras 999 px.
Alturas mínimas: botones e inputs 44–54 px (objetivo táctil ≥ 44 px).

### Tipografía (Google Fonts)

| Familia | Uso |
|---|---|
| **Cormorant Garamond** 500/600, cursiva 500 | Títulos (`h1` 52–76 px, `h2` 28–44 px), con `text-shadow: 0 0 36px rgba(224,30,60,.3)` |
| **Manrope** 400–700 | Interfaz y texto |
| **JetBrains Mono** 400/500 | Códigos `INC-0042`, rutas `~/incidentes`, etiquetas en mayúsculas con `letter-spacing: 2–3px`, auditoría |

### Glifos de fondo

Katakana y dígitos en posiciones aleatorias que **aparecen, brillan y se desvanecen** (no caen
como lluvia). Unos 60 en login y registro y unos 30 en el resto. Un 20 % dorados
(`rgba(240,201,135,.45)`), el resto carmesí (`rgba(255,77,94,.5)`). Cada 700 ms cambian de
carácter unos pocos. Animación `aparecer` con duración aleatoria de 4–10 s y retraso negativo.
Con `prefers-reduced-motion` se quedan quietos al 20 % de opacidad. La capa va con
`aria-hidden="true"` y `pointer-events: none`.

---

## Pantallas y API

| Pantalla | Archivo | Endpoints |
|---|---|---|
| Login | `Main.dc.html` | `POST /auth/login` (errores 401 y 429) |
| Registro | `Registro.dc.html` | `POST /auth/registro` (mín. 12 caracteres) |
| Listado | `Incidentes.dc.html` | `GET /incidentes` con filtros y paginación. Contadores: `GET /incidentes?estado=X&limite=1` → `total` |
| Nuevo incidente | `NuevoIncidente.dc.html` | `POST /incidentes` (422 por campo) |
| Detalle | `Detalle.dc.html` | `GET`/`PATCH /incidentes/{id}`, `/estado`, `/notas`, `/asignar`, `DELETE` |
| Usuarios (admin) | `Usuarios.dc.html` | `GET /usuarios?rol=&email=`, `PATCH /usuarios/{id}/rol`, `PATCH /usuarios/{id}/activo` |
| Auditoría (admin) | `Auditoria.dc.html` | `GET /auditoria?accion=` |
| Estados | `Estados.dc.html` | 401 · 404 · 409 · 500/503 · vacío · cargando |
| Mi cuenta | `Cuenta.dc.html` | `GET /usuarios/yo`, `PATCH /usuarios/yo/contrasena` |

### Qué muestra el detalle según el rol

| Bloque | reportante | analista asignado | admin |
|---|---|---|---|
| Editar título/descripción/categoría | solo en `abierto` | — | ✅ |
| Notas internas | nunca | ✅ | ✅ |
| Cambiar estado | — | ✅ | ✅ (y reabrir desde `cerrado`) |
| Asignar analista · Borrar | — | — | ✅ |

La interfaz solo **oculta** acciones; quien decide es la API. Un 403/404/409 de la API se
muestra siempre, aunque el botón no debiera haber aparecido.

### Reglas de interfaz que vienen de la seguridad

- **404 = «no existe»**, aunque sea un recurso ajeno. Nunca distinguir entre «no existe» y «no tienes acceso».
- **401:** primero un `POST /auth/refrescar` silencioso; si falla, se borran los tokens y se vuelve al login.
- **Tokens en memoria**, no en `localStorage` (XSS). El refresco es lo único que podría persistir, y hay que decidir dónde antes de implementar.
- **Las notas internas** no se piden ni se pintan para el reportante: la API ya no las envía.
- La auditoría muestra en rojo `login_fallido`, `reutilizacion_token` y `cambio_contrasena_fallido`; en oro `cambio_rol`, `asignar_incidente`, `borrar_incidente`, `desactivar_usuario` y `reactivar_usuario`.
- **CORS:** el origen del front tiene que estar en `CORS_ORIGENES` de la API.
