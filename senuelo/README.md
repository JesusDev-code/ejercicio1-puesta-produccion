# Señuelo y generador de eventos

Dos papeles de la **misma imagen** (lo elige la variable `MODO`), sin frontend y **sin una
sola dependencia** de Python. Alimentan el panel de monitorización de la web de incidencias.

| `MODO` | Qué hace | Puerto | Dominio en Dokploy |
|---|---|---|---|
| `senuelo` | Honeypot de registro: recibe peticiones de internet, las clasifica y las manda a la API como eventos. **No es vulnerable**: no sirve ficheros ni ejecuta nada, solo responde un 404 genérico. | 8000 | sí (uno propio) |
| `generador` | Fabrica eventos de **demostración** (telemetría de mentira que imita el ruido de sondeo de internet) para que el panel tenga datos en vivo. | — | no |

## Variables de entorno

| Variable | Para | Descripción |
|---|---|---|
| `MODO` | ambos | `senuelo` (por defecto) o `generador` |
| `API_URL` | ambos | URL **interna** de la API, p. ej. `http://api:8000` (sin `/api`) |
| `INGESTA_TOKEN` | ambos | El mismo token que `INGESTA_TOKEN` de la API |
| `PUERTO` | señuelo | Puerto de escucha (por defecto 8000) |
| `INTERVALO_MIN` / `INTERVALO_MAX` | generador | Segundos entre tandas de eventos (1.5–6 por defecto) |

## Por qué el señuelo es seguro

- No sirve ficheros del disco ni ejecuta comandos: toda petición recibe el mismo 404.
- No lee el cuerpo de la petición (evita tragarse megas de basura).
- Solo guarda método, ruta y user-agent, y la API los trunca y limpia antes de almacenarlos.
- Corre sin root, con el sistema de ficheros en solo lectura y sin capabilities.

El riesgo de una caja realmente vulnerable expuesta a internet (que se la queden y pivoten
hacia el resto del VPS) **no existe aquí**: no hay nada que explotar, solo un registrador.

## Tests y lint

El señuelo no tiene dependencias propias, así que se valida con las herramientas del backend
(`ruff.toml` hereda la configuración de `backend/pyproject.toml`). Desde `backend/`:

```bash
uv run ruff check ../senuelo && uv run ruff format --check ../senuelo
uv run pytest ../senuelo        # 12 tests del clasificador, sin red
```

## Desarrollo local

```bash
# Con la API en 127.0.0.1:8000 y su INGESTA_TOKEN configurado:
API_URL=http://127.0.0.1:8000 INGESTA_TOKEN=... MODO=generador python arranque.py
API_URL=http://127.0.0.1:8000 INGESTA_TOKEN=... PUERTO=9000 python arranque.py   # señuelo
```
