import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import obtener_configuracion
from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# La URL sale de la configuración de la app (variables de entorno), nunca de alembic.ini
URL = obtener_configuracion().database_url
# SQLite no admite la mayoría de ALTER TABLE: Alembic recrea la tabla en modo batch
ES_SQLITE = URL.startswith("sqlite")


def _configurar(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=ES_SQLITE,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Genera el SQL sin conectar (`alembic upgrade head --sql`)."""
    _configurar(url=URL, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    _configurar(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    motor = create_async_engine(URL, poolclass=pool.NullPool)
    async with motor.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await motor.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif (conexion := config.attributes.get("connection")) is not None:
    # Los tests pasan su propia conexión: se reutiliza en vez de abrir otra
    do_run_migrations(conexion)
else:
    asyncio.run(run_async_migrations())
