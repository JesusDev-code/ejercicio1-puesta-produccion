import enum
import secrets
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def ahora() -> datetime:
    return datetime.now(UTC)


def a_utc(fecha: datetime) -> datetime:
    """SQLite devuelve fechas sin zona horaria; se normaliza todo a UTC."""
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)


class Rol(enum.StrEnum):
    usuario = "usuario"  # trabajador de una empresa cliente: ve lo que él reporta
    gestor = "gestor"  # responsable de una empresa cliente: ve y gestiona su empresa
    analista = "analista"  # personal de Kaelum: analiza lo que le asignan
    admin = "admin"  # personal de Kaelum: todo


# Personal del MSSP: cruza clientes, así que NUNCA pertenece a una empresa. Que alguien sea
# personal lo decide su rol, jamás la ausencia de empresa (una cuenta recién registrada
# tampoco tiene empresa y no por eso puede ver a todos los clientes).
ROLES_PERSONAL = frozenset({Rol.admin, Rol.analista})
# Trabajan para una empresa cliente: sin ella, la cuenta está pendiente de unirse a una
ROLES_CLIENTE = frozenset({Rol.usuario, Rol.gestor})

# Hash de una cuenta sin contraseña (solo entra con Google o GitHub). No es un hash argon2
# válido: verificar_contrasena siempre falla contra él
SIN_CONTRASENA = "!"

# Sin 0/O ni 1/I/L: el código se dicta o se copia a mano. 31 símbolos ^ 12 ≈ 59 bits
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_codigo_invitacion() -> str:
    """XXXX-XXXX-XXXX. Con 5 intentos por minuto, adivinarlo por fuerza bruta es inviable."""
    simbolos = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(12))
    return "-".join(simbolos[i : i + 4] for i in range(0, 12, 4))


def normalizar_codigo_invitacion(codigo: str) -> str:
    """Admite el código en minúsculas, sin guiones o con espacios, como lo teclee la gente."""
    limpio = "".join(c for c in codigo.upper() if c in _ALFABETO_CODIGO)
    return "-".join(limpio[i : i + 4] for i in range(0, len(limpio), 4))


class Estado(enum.StrEnum):
    abierto = "abierto"
    en_analisis = "en_analisis"
    resuelto = "resuelto"
    cerrado = "cerrado"


class Severidad(enum.StrEnum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class Categoria(enum.StrEnum):
    phishing = "phishing"
    malware = "malware"
    acceso_no_autorizado = "acceso_no_autorizado"
    fuga_datos = "fuga_datos"
    denegacion_servicio = "denegacion_servicio"
    otro = "otro"


class EstadoTriaje(enum.StrEnum):
    """Triaje del analista sobre un evento: separa el ruido de lo que merece atención."""

    nuevo = "nuevo"
    revisado = "revisado"
    ignorado = "ignorado"


class TipoEvento(enum.StrEnum):
    """Clasificación defensiva de lo que detecta el señuelo, como una regla de un WAF."""

    sondeo_rutas = "sondeo_rutas"  # busca paneles de administración o rutas conocidas
    fichero_sensible = "fichero_sensible"  # pide .env, .git, copias de seguridad...
    fuerza_bruta = "fuerza_bruta"  # intentos repetidos de inicio de sesión
    inyeccion = "inyeccion"  # patrones de SQLi o XSS en la petición
    recorrido_rutas = "recorrido_rutas"  # ../ para salir del directorio servido
    escaner = "escaner"  # user-agent de una herramienta de escaneo conocida
    otro = "otro"


def _enum(tipo: type[enum.Enum]) -> Enum:
    return Enum(
        tipo,
        native_enum=False,
        create_constraint=True,
        length=30,
        values_callable=lambda e: [m.value for m in e],
    )


class Empresa(Base):
    """Cliente del MSSP. `codigo` es el identificador estable que usan los sensores para
    declarar de quién es un evento: no se edita nunca, el nombre sí."""

    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    sector: Mapped[str | None] = mapped_column(String(80))
    activa: Mapped[bool] = mapped_column(default=True)
    # Lo reparte el gestor a sus trabajadores para que se unan tras registrarse. Se guarda en
    # claro porque el gestor tiene que poder verlo; si se filtra, se regenera y el viejo muere
    codigo_invitacion: Mapped[str] = mapped_column(
        String(14), unique=True, index=True, default=generar_codigo_invitacion
    )
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[Rol] = mapped_column(_enum(Rol), default=Rol.usuario)
    # Personal del MSSP: siempre None. Usuario o gestor: su empresa, o None mientras está
    # pendiente (recién registrado, aún sin unirse con un código de invitación)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    activo: Mapped[bool] = mapped_column(default=True)
    # Va en cada access token (claim "ver"). Subirla invalida al momento todos los tokens ya
    # emitidos, sin esperar a que caduquen: cambio de contraseña, restablecimiento, rol, baja
    version_sesion: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    # MFA (TOTP). Los secretos van cifrados con MFA_CLAVE: una copia de la BD sola no basta para
    # generar códigos. `mfa_pendiente` es el que se está dando de alta, aún sin confirmar
    mfa_secreto: Mapped[str | None] = mapped_column(String(255))
    mfa_pendiente: Mapped[str | None] = mapped_column(String(255))
    # Último paso de 30 s aceptado: un código ya usado no vale una segunda vez (anti-replay)
    mfa_ultimo_paso: Mapped[int | None] = mapped_column(Integer)
    # Fallos seguidos del segundo factor. Al quinto, bloqueo temporal: quien tiene la contraseña
    # no puede probar el millón de códigos posibles cambiando de IP
    mfa_fallos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    mfa_bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def es_personal(self) -> bool:
        return self.rol in ROLES_PERSONAL

    @property
    def mfa_activo(self) -> bool:
        return self.mfa_secreto is not None

    @property
    def tiene_contrasena(self) -> bool:
        return self.hash_contrasena != SIN_CONTRASENA

    @property
    def pendiente(self) -> bool:
        """Cuenta de cliente sin empresa: solo puede ver su cuenta y unirse a una empresa."""
        return self.rol in ROLES_CLIENTE and self.empresa_id is None


class Incidente(Base):
    __tablename__ = "incidentes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(Text)
    severidad: Mapped[Severidad] = mapped_column(_enum(Severidad))
    categoria: Mapped[Categoria] = mapped_column(_enum(Categoria))
    estado: Mapped[Estado] = mapped_column(_enum(Estado), default=Estado.abierto, index=True)
    reportante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    analista_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    # Se copia del reportante (o del evento de origen) al crearla y no cambia después
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    notas_internas: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora, onupdate=ahora
    )
    borrado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TokenRefresco(Base):
    __tablename__ = "tokens_refresco"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    hash_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    familia_id: Mapped[str] = mapped_column(String(64), index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revocado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CodigoRecuperacion(Base):
    """Códigos de un solo uso para entrar sin el móvil. Solo el hash: se enseñan una vez."""

    __tablename__ = "codigos_recuperacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    hash_codigo: Mapped[str] = mapped_column(String(64), index=True)
    usado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdentidadExterna(Base):
    """Cuenta de Google o GitHub vinculada a un usuario. Se busca SIEMPRE por (proveedor,
    sujeto): el email de un proveedor puede cambiar o reasignarse, el identificador no."""

    __tablename__ = "identidades_externas"
    __table_args__ = (UniqueConstraint("proveedor", "sujeto"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    proveedor: Mapped[str] = mapped_column(String(20))
    sujeto: Mapped[str] = mapped_column(String(255))
    # El email con el que se vinculó, solo informativo
    email: Mapped[str] = mapped_column(String(254))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class RegistroAuditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    accion: Mapped[str] = mapped_column(String(50), index=True)
    recurso: Mapped[str] = mapped_column(String(50))
    recurso_id: Mapped[int | None] = mapped_column(Integer)
    ip: Mapped[str | None] = mapped_column(String(45))
    detalle: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)


class EventoSeguridad(Base):
    """Un evento detectado por el señuelo (o generado para la demo). Los campos que vienen de
    internet (ruta, agente...) no se editan nunca; solo el triaje del analista (estado y nota).
    Los campos de texto no son de fiar: la API los limpia y los trunca antes de guardarlos."""

    __tablename__ = "eventos_seguridad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, index=True)
    origen_ip: Mapped[str] = mapped_column(String(45), index=True)
    tipo: Mapped[TipoEvento] = mapped_column(_enum(TipoEvento), index=True)
    severidad: Mapped[Severidad] = mapped_column(_enum(Severidad))
    metodo: Mapped[str] = mapped_column(String(10))
    ruta: Mapped[str] = mapped_column(String(512))
    agente: Mapped[str | None] = mapped_column(String(512))
    servicio: Mapped[str] = mapped_column(String(64))
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    detalle: Mapped[str | None] = mapped_column(String(1000))
    estado_triaje: Mapped[EstadoTriaje] = mapped_column(
        _enum(EstadoTriaje), default=EstadoTriaje.nuevo, index=True
    )
    nota: Mapped[str | None] = mapped_column(String(1000))
    incidente_id: Mapped[int | None] = mapped_column(ForeignKey("incidentes.id"), index=True)
