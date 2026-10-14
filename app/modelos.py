import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def ahora() -> datetime:
    return datetime.now(UTC)


def a_utc(fecha: datetime) -> datetime:
    """SQLite devuelve fechas sin zona horaria; se normaliza todo a UTC."""
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)


class Rol(enum.StrEnum):
    usuario = "usuario"
    analista = "analista"
    admin = "admin"


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


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    hash_contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[Rol] = mapped_column(_enum(Rol), default=Rol.usuario)
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


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
    detalle: Mapped[str | None] = mapped_column(String(1000))
    estado_triaje: Mapped[EstadoTriaje] = mapped_column(
        _enum(EstadoTriaje), default=EstadoTriaje.nuevo, index=True
    )
    nota: Mapped[str | None] = mapped_column(String(1000))
    incidente_id: Mapped[int | None] = mapped_column(ForeignKey("incidentes.id"), index=True)
