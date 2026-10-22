from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: Literal["desarrollo", "produccion", "test"] = "desarrollo"
    database_url: str = "postgresql+asyncpg://incidentes:incidentes@localhost:5432/incidentes"

    jwt_secreto: str = Field(min_length=32)
    jwt_algoritmo: str = "HS256"
    acceso_minutos: int = 15
    refresco_dias: int = 7

    # Lista separada por comas, p. ej. "https://app.example.com,http://localhost:4321"
    cors_origenes: str = ""

    # Prefijo bajo el que el proxy publica la API (/api). La API lo quita ella misma, así no
    # depende de que el proxy haga "strip path". Vacío = sin prefijo.
    api_prefijo: str = Field(default="", pattern=r"^(/[A-Za-z0-9_-]+)?$")

    # Path de la cookie de refresco tal como la ve el NAVEGADOR. Si un proxy publica la API
    # bajo un prefijo (Traefik con strip path en /api), aquí va ese prefijo: /api/auth/web
    cookie_refresco_ruta: str = Field(default="/auth/web", pattern=r"^/[A-Za-z0-9/_-]*$")

    # Token de servicio para POST /eventos (señuelo y generador). Vacío = ingesta desactivada.
    # No es un JWT de usuario: lo comparten servicios de confianza dentro del mismo compose.
    ingesta_token: str = Field(default="", pattern=r"^$|^.{32,}$")
    eventos_retencion_dias: int = Field(default=30, ge=1, le=365)

    limite_auth: str = "5/minute"
    limitador_activo: bool = True

    # Cifra los secretos TOTP en la BD (AES-GCM). Distinta de JWT_SECRETO: rotar una no rompe la
    # otra. Si se pierde, ningún MFA vuelve a validar: habría que restablecerlos todos
    mfa_clave: str = Field(min_length=32)
    # MFA opcional para todos por defecto. Con true, el personal del MSSP (admin, analista), que
    # cruza clientes, no ve nada hasta activarlo y no puede desactivarlo
    mfa_obligatorio_personal: bool = False

    # URL pública de la web (https://umbral.example.com), sin barra final. La necesita OAuth para
    # construir el redirect_uri y volver al front. Vacía = login con Google y GitHub desactivado
    url_publica: str = Field(default="", pattern=r"^$|^https?://[A-Za-z0-9.-]+(:\d+)?$")
    # Path de la cookie del flujo OAuth (state + PKCE), como la ve el navegador
    cookie_oauth_ruta: str = Field(default="/auth/oauth", pattern=r"^/[A-Za-z0-9/_-]*$")
    # Cada proveedor se activa solo si tiene id y secreto
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()  # type: ignore[call-arg]
