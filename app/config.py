from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: Literal["desarrollo", "produccion", "test"] = "desarrollo"
    database_url: str = "postgresql+asyncpg://incidentes:incidentes@localhost:5432/incidentes"

    # Firebase Authentication. Las credenciales (JSON de la cuenta de servicio, en base64) son
    # SECRETAS y solo las recibe la API. Las otras tres son la config web, que es pública.
    firebase_credenciales: str = ""
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_project_id: str = ""
    # Emulador de Firebase Auth (host:puerto) para los E2E. El Admin SDK lee esta misma variable
    # del entorno y, con ella, ACEPTA TOKENS SIN FIRMAR: en producción está prohibida.
    firebase_auth_emulator_host: str = ""

    # Lista separada por comas, p. ej. "https://app.example.com,http://localhost:4321"
    cors_origenes: str = ""

    # Prefijo bajo el que el proxy publica la API (/api). La API lo quita ella misma, así no
    # depende de que el proxy haga "strip path". Vacío = sin prefijo.
    api_prefijo: str = Field(default="", pattern=r"^(/[A-Za-z0-9_-]+)?$")

    # Token de servicio para POST /eventos (señuelo y generador). Vacío = ingesta desactivada.
    # No es un JWT de usuario: lo comparten servicios de confianza dentro del mismo compose.
    ingesta_token: str = Field(default="", pattern=r"^$|^.{32,}$")
    eventos_retencion_dias: int = Field(default=30, ge=1, le=365)

    limite_auth: str = "5/minute"
    limitador_activo: bool = True

    @model_validator(mode="after")
    def firebase_en_produccion(self) -> "Configuracion":
        # Sin credenciales nadie podría entrar: mejor no arrancar que arrancar rota
        if self.entorno == "produccion" and not (
            self.firebase_credenciales and self.firebase_api_key and self.firebase_project_id
        ):
            raise ValueError("En producción faltan FIREBASE_CREDENCIALES, _API_KEY o _PROJECT_ID")
        if self.entorno == "produccion" and self.firebase_auth_emulator_host:
            raise ValueError("FIREBASE_AUTH_EMULATOR_HOST no se puede usar en producción")
        return self

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()  # type: ignore[call-arg]
