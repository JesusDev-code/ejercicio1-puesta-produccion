import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import obtener_configuracion
from app.errores import ErrorDominio, NoAutenticado
from app.limitador import limitador
from app.routers import auditoria, auth, eventos, incidentes, salud, usuarios

log = logging.getLogger("app")
config = obtener_configuracion()

app = FastAPI(
    title="API de incidentes de ciberseguridad",
    version="0.1.0",
    # En producción no se publica el mapa de la API
    docs_url=None if config.es_produccion else "/docs",
    redoc_url=None,
    openapi_url=None if config.es_produccion else "/openapi.json",
)

app.state.limiter = limitador
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.lista_cors,
    allow_credentials=False,  # se usa Bearer, no cookies
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_CABECERAS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
_CSP = "default-src 'none'; frame-ancestors 'none'"


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.update(_CABECERAS)
    # Swagger UI necesita cargar scripts: la CSP estricta se omite solo en /docs (no existe en prod)
    if not request.url.path.startswith("/docs"):
        respuesta.headers["Content-Security-Policy"] = _CSP
    return respuesta


@app.exception_handler(ErrorDominio)
async def manejar_error_dominio(_: Request, error: ErrorDominio):
    cabeceras = {"WWW-Authenticate": "Bearer"} if isinstance(error, NoAutenticado) else None
    return JSONResponse({"detail": error.detalle}, status_code=error.codigo, headers=cabeceras)


@app.exception_handler(Exception)
async def manejar_error_inesperado(_: Request, error: Exception):
    # La traza va al log del servidor, nunca al cliente
    log.exception("Error no controlado", exc_info=error)
    return JSONResponse({"detail": "Error interno"}, status_code=500)


for modulo in (auth, usuarios, incidentes, auditoria, eventos, salud):
    app.include_router(modulo.router)


class QuitarPrefijo:
    """Middleware ASGI: /api/salud -> /salud. Las rutas sin el prefijo siguen funcionando,
    así que vale tanto si el proxy ya lo quitó (strip path) como si no."""

    def __init__(self, app, prefijo: str):
        self.app = app
        self.prefijo = prefijo

    async def __call__(self, scope, receive, send):
        if self.prefijo and scope["type"] == "http":
            ruta = scope["path"]
            if ruta == self.prefijo or ruta.startswith(self.prefijo + "/"):
                nueva = ruta[len(self.prefijo) :] or "/"
                scope = {**scope, "path": nueva, "raw_path": nueva.encode()}
        await self.app(scope, receive, send)


app.add_middleware(QuitarPrefijo, prefijo=config.api_prefijo)
