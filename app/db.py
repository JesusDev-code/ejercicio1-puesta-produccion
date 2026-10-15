from collections.abc import AsyncIterator

from sqlalchemy import MetaData, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, StaticPool

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    # Nombres de restricciones deterministas: Alembic los necesita para poder borrarlas o
    # alterarlas, y evita que dos CHECK de tablas distintas se llamen igual ("rol", "estado")
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _crear_motor():
    url = obtener_configuracion().database_url
    if url.startswith("sqlite") and _en_memoria(url):
        # SQLite en memoria (tests): una única conexión compartida, o cada sesión vería una BD
        # vacía distinta. SOLO aquí: con peticiones concurrentes, sus transacciones se mezclan
        return create_async_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    if url.startswith("sqlite"):
        # SQLite en fichero (E2E): una conexión por sesión, aislada como en PostgreSQL
        return create_async_engine(url, poolclass=NullPool)
    return create_async_engine(url, pool_pre_ping=True)


def _en_memoria(url: str) -> bool:
    ruta = make_url(url).database
    return not ruta or ruta == ":memory:"


motor = _crear_motor()
FabricaSesion = async_sessionmaker(motor, expire_on_commit=False)


async def obtener_sesion() -> AsyncIterator[AsyncSession]:
    async with FabricaSesion() as sesion:
        yield sesion
