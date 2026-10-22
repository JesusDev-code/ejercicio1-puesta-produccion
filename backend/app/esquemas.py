"""Esquemas Pydantic. Entrada y salida van separados: ningún esquema de entrada acepta
campos como `rol`, `estado` o `reportante_id`, y `extra="forbid"` rechaza los desconocidos."""

from datetime import datetime
from ipaddress import ip_address
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modelos import Categoria, Estado, EstadoTriaje, Rol, Severidad, TipoEvento


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Autenticación ---


class LoginEntrada(Entrada):
    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=128)


class RegistroEntrada(Entrada):
    """Registro público: solo email y contraseña. Ni rol ni empresa: la cuenta nace como
    usuario pendiente y la empresa se elige después con un código de invitación."""

    email: EmailStr
    contrasena: str = Field(min_length=12, max_length=128)


class RegistroSalida(BaseModel):
    # Mismo mensaje exista o no el email: el registro no revela qué cuentas hay
    mensaje: str = "Si el email es válido, la cuenta queda creada. Ya puedes iniciar sesión."


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


class DesafioMfa(BaseModel):
    """Respuesta del login cuando la cuenta tiene MFA: todavía no hay sesión, solo un desafío
    que se canjea en /auth/mfa junto con un código."""

    mfa_requerido: Literal[True] = True
    desafio: str
    expira_en_segundos: int


# Seis dígitos del autenticador o un código de recuperación (XXXX-XXXX-XXXX, con o sin guiones)
CodigoMfa = Field(min_length=6, max_length=30)


class MfaEntrada(Entrada):
    desafio: str = Field(min_length=1, max_length=1024)
    codigo: str = CodigoMfa


class ReautenticacionEntrada(Entrada):
    """Prueba fresca de identidad: un access token robado no basta para cambiar cómo se entra.

    Con contraseña, la contraseña. Sin ella (solo Google o GitHub): un código MFA si lo tiene
    activo, o haber iniciado sesión hace menos de 5 minutos."""

    contrasena: str | None = Field(default=None, min_length=1, max_length=128)
    codigo: str | None = Field(default=None, min_length=6, max_length=30)


class MfaAlta(BaseModel):
    """Secreto nuevo, aún sin activar. `qr` son las filas de la matriz ("1" = módulo oscuro):
    el front la dibuja como SVG sin imágenes ni HTML inyectado (CSP y Trusted Types)."""

    secreto: str
    uri: str
    qr: list[str]


class CodigoEntrada(Entrada):
    codigo: str = CodigoMfa


class MfaDesactivarEntrada(Entrada):
    contrasena: str | None = Field(default=None, min_length=1, max_length=128)
    codigo: str = CodigoMfa


class CodigosRecuperacion(BaseModel):
    """Se enseñan UNA vez: en la BD solo queda su hash."""

    codigos: list[str]


class ProveedoresOAuth(BaseModel):
    proveedores: list[str]


class UrlOAuth(BaseModel):
    """A dónde mandar al navegador para vincular el proveedor."""

    url: str


# --- Empresas (clientes del MSSP) ---

CODIGO_EMPRESA = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class EmpresaCrear(Entrada):
    codigo: str = Field(min_length=2, max_length=40, pattern=CODIGO_EMPRESA)
    nombre: str = Field(min_length=2, max_length=120)
    sector: str | None = Field(default=None, max_length=80)


class EmpresaEditar(Entrada):
    """El código no se edita: es lo que los sensores declaran en cada evento."""

    nombre: str | None = Field(default=None, min_length=2, max_length=120)
    sector: str | None = Field(default=None, max_length=80)
    activa: bool | None = None


class EmpresaSalida(Salida):
    """Solo la ven el admin y el gestor de la empresa: por eso puede llevar el código."""

    id: int
    codigo: str
    nombre: str
    sector: str | None
    activa: bool
    codigo_invitacion: str
    creada_en: datetime


class UnirseEmpresaEntrada(Entrada):
    # Holgado a propósito: se admite con espacios, guiones o en minúsculas y se normaliza
    codigo: str = Field(min_length=12, max_length=30)


# --- Usuarios ---


class UsuarioSalida(Salida):
    id: int
    email: EmailStr
    rol: Rol
    empresa_id: int | None
    activo: bool
    # Cuenta de cliente aún sin empresa: el front la manda a «Unirme a mi empresa»
    pendiente: bool
    mfa_activo: bool
    creado_en: datetime


class UsuarioYo(UsuarioSalida):
    """La propia cuenta: además, el nombre de su empresa para que sepa a cuál pertenece.

    Solo el nombre: el código de invitación es cosa del gestor (/mi-empresa).
    """

    empresa_nombre: str | None = None
    # False si solo entra con Google o GitHub: no hay contraseña que cambiar ni que pedir
    tiene_contrasena: bool
    # Su rol exige MFA (no puede desactivarlo) y, si aún no lo tiene, hasta activarlo solo ve
    # su cuenta
    mfa_obligatorio: bool = False
    mfa_por_activar: bool = False
    proveedores: list[str] = []


class UsuarioCrear(Entrada):
    """Alta de cuentas por un admin, con el rol y la empresa que él decida."""

    email: EmailStr
    contrasena: str = Field(min_length=12, max_length=128)
    rol: Rol = Rol.usuario
    # Admin y analista: sin empresa (personal del MSSP). Usuario y gestor: con la suya
    empresa_id: int | None = Field(default=None, gt=0)


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
    empresa_id: int | None
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


# --- Eventos de seguridad ---

_CONTROL = dict.fromkeys(range(32))  # caracteres de control: fuera (inyección en logs)


def _limpiar(valor: str | None, maximo: int) -> str | None:
    if valor is None:
        return None
    return valor.translate(_CONTROL)[:maximo]


class EventoEntrada(Entrada):
    """Lo que manda el señuelo. Se trunca en vez de rechazar: un evento con una ruta de
    2000 caracteres es justo el tipo de cosa que interesa registrar."""

    origen_ip: str = Field(max_length=45)
    tipo: TipoEvento
    severidad: Severidad
    metodo: str = Field(min_length=1, max_length=10)
    ruta: str = Field(min_length=1, max_length=4096)
    agente: str | None = Field(default=None, max_length=4096)
    servicio: str = Field(default="senuelo", min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    # Código del cliente al que pertenece el sensor; sin él, el evento es del propio MSSP
    empresa: str | None = Field(default=None, max_length=40, pattern=CODIGO_EMPRESA)
    detalle: str | None = Field(default=None, max_length=4096)

    @field_validator("origen_ip")
    @classmethod
    def ip_valida(cls, v: str) -> str:
        return str(ip_address(v))

    @field_validator("metodo")
    @classmethod
    def metodo_limpio(cls, v: str) -> str:
        return v.upper().translate(_CONTROL)[:10]

    @field_validator("ruta")
    @classmethod
    def ruta_limpia(cls, v: str) -> str:
        return _limpiar(v, 512) or "/"

    @field_validator("agente")
    @classmethod
    def agente_limpio(cls, v: str | None) -> str | None:
        return _limpiar(v, 512)

    @field_validator("detalle")
    @classmethod
    def detalle_limpio(cls, v: str | None) -> str | None:
        return _limpiar(v, 1000)


class LoteEventos(Entrada):
    eventos: list[EventoEntrada] = Field(min_length=1, max_length=100)


class EventoSalida(Salida):
    id: int
    fecha: datetime
    origen_ip: str
    tipo: TipoEvento
    severidad: Severidad
    metodo: str
    ruta: str
    agente: str | None
    servicio: str
    empresa_id: int | None
    detalle: str | None
    estado_triaje: EstadoTriaje
    nota: str | None
    incidente_id: int | None


class TriajeEntrada(Entrada):
    """Lo editable de un evento. Ambos campos opcionales: se puede cambiar solo uno."""

    estado: EstadoTriaje | None = None
    nota: str | None = Field(default=None, max_length=1000)


class Recuento(BaseModel):
    clave: str
    total: int


class Tramo(BaseModel):
    inicio: datetime
    total: int


class Sensor(BaseModel):
    """Un sensor es la pareja (servicio, empresa) que firma los eventos: no hay registro de
    sensores aparte, se deducen de lo que llega."""

    servicio: str
    empresa_id: int | None
    total: int
    ultimas_24h: int
    ultimo: datetime


class ResumenEventos(BaseModel):
    horas: int
    total: int
    ultima_hora: int
    ips_unicas: int
    criticos: int
    por_tipo: list[Recuento]
    por_severidad: list[Recuento]
    top_ips: list[Recuento]
    por_minuto: list[Tramo]  # últimos 60 minutos, uno por minuto
    por_hora: list[Tramo]  # últimas 168 horas (7 días), una por hora
