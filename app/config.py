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

    limite_auth: str = "5/minute"
    limitador_activo: bool = True

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()  # type: ignore[call-arg]
