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
