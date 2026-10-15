"""Esquemas Pydantic. Entrada y salida van separados: ningún esquema de entrada acepta
campos como `rol`, `estado` o `reportante_id`, y `extra="forbid"` rechaza los desconocidos."""

from datetime import datetime
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modelos import Categoria, Estado, EstadoTriaje, Rol, Severidad, TipoEvento


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Configuración pública para el front ---


class ConfigFirebase(BaseModel):
    """Config web de Firebase: no es secreta, la ve cualquier navegador que cargue la app."""

    apiKey: str  # noqa: N815 - nombres que espera el SDK de Firebase
    authDomain: str  # noqa: N815
    projectId: str  # noqa: N815
    # Solo en local/E2E: el front se conecta al emulador en vez de a Google
    emulador: str | None = None


class ConfigCliente(BaseModel):
    firebase: ConfigFirebase


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
    id: int
    codigo: str
    nombre: str
    sector: str | None
    activa: bool
    creada_en: datetime


# --- Usuarios ---


class UsuarioSalida(Salida):
    id: int
    email: EmailStr
    rol: Rol
    empresa_id: int | None
    activo: bool
    creado_en: datetime


class UsuarioCrear(Entrada):
    """Alta de cuentas: solo la hace un admin. No hay registro público."""

    email: EmailStr
    contrasena: str = Field(min_length=12, max_length=128)
    rol: Rol = Rol.usuario
    # Sin empresa = personal del MSSP. Admin y analista no pueden tener empresa
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
