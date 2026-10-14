"""Esquemas Pydantic. Entrada y salida van separados: ningún esquema de entrada acepta
campos como `rol`, `estado` o `reportante_id`, y `extra="forbid"` rechaza los desconocidos."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modelos import Categoria, Estado, Rol, Severidad


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Autenticación ---


class LoginEntrada(Entrada):
    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class RefrescoEntrada(Entrada):
    token_refresco: str = Field(min_length=1, max_length=256)


class ParTokens(BaseModel):
    token_acceso: str
    token_refresco: str
    tipo_token: str = "bearer"  # noqa: S105
    expira_en_segundos: int


class TokenAcceso(BaseModel):
    """Respuesta de las rutas /auth/web: el refresco viaja en una cookie HttpOnly, nunca en el
    cuerpo, para que el JavaScript del navegador (y un XSS) no pueda leerlo."""

    token_acceso: str
    tipo_token: str = "bearer"  # noqa: S105
    expira_en_segundos: int


# --- Usuarios ---


class UsuarioSalida(Salida):
    id: int
    email: EmailStr
    rol: Rol
    activo: bool
    creado_en: datetime


class UsuarioCrear(Entrada):
    """Alta de cuentas: solo la hace un admin. No hay registro público."""

    email: EmailStr
    contrasena: str = Field(min_length=12, max_length=128)
    rol: Rol = Rol.usuario


class RestablecerContrasenaEntrada(Entrada):
    contrasena_nueva: str = Field(min_length=12, max_length=128)


class CambioRolEntrada(Entrada):
    rol: Rol


class CambioActivoEntrada(Entrada):
    activo: bool


class CambioContrasenaEntrada(Entrada):
    contrasena_actual: str = Field(min_length=1, max_length=128)
    contrasena_nueva: str = Field(min_length=12, max_length=128)


# --- Incidentes ---


class IncidenteCrear(Entrada):
    titulo: str = Field(min_length=3, max_length=120)
    descripcion: str = Field(min_length=1, max_length=5000)
    severidad: Severidad
    categoria: Categoria


class IncidenteEditar(Entrada):
    titulo: str | None = Field(default=None, min_length=3, max_length=120)
    descripcion: str | None = Field(default=None, min_length=1, max_length=5000)
    categoria: Categoria | None = None


class CambioEstadoEntrada(Entrada):
    estado: Estado


class AsignacionEntrada(Entrada):
    analista_id: int = Field(gt=0)


class NotasEntrada(Entrada):
    notas_internas: str = Field(max_length=10000)


class IncidenteSalida(Salida):
    """Lo que ve el reportante: sin notas internas."""

    id: int
    titulo: str
    descripcion: str
    severidad: Severidad
    categoria: Categoria
    estado: Estado
    reportante_id: int
    analista_id: int | None
    # No son columnas del incidente: el router los resuelve con una consulta aparte
    reportante_email: str | None = None
    analista_email: str | None = None
    creado_en: datetime
    actualizado_en: datetime


class IncidenteSalidaInterna(IncidenteSalida):
    """Lo que ven el analista asignado y el admin."""

    notas_internas: str | None


class Pagina[T](BaseModel):
    total: int
    limite: int
    desplazamiento: int
    elementos: list[T]


# --- Auditoría ---


class AuditoriaSalida(Salida):
    id: int
    usuario_id: int | None
    usuario_email: str | None = None
    accion: str
    recurso: str
    recurso_id: int | None
    ip: str | None
    detalle: str | None
    fecha: datetime
