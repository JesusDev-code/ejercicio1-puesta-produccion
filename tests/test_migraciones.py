import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from alembic import command
from app.db import Base, motor


@pytest.fixture
async def bd():
    """Sustituye al fixture global: aquí el esquema lo crea Alembic, no create_all."""
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
    yield
    async with motor.begin() as conexion:
        await conexion.run_sync(lambda c: c.exec_driver_sql("DROP TABLE IF EXISTS alembic_version"))
        await conexion.run_sync(Base.metadata.drop_all)
    await motor.dispose()


def _alembic(conexion):
    config = Config("alembic.ini")
    config.attributes["connection"] = conexion
    return config


async def test_las_migraciones_coinciden_con_los_modelos():
    # Si alguien cambia un modelo y olvida la migración, este test falla
    async with motor.begin() as conexion:
        await conexion.run_sync(lambda c: command.upgrade(_alembic(c), "head"))
        diferencias = await conexion.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata)
        )
        tablas = await conexion.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert diferencias == []
    assert {"usuarios", "incidentes", "empresas", "auditoria"} <= tablas
    assert "tokens_refresco" not in tablas  # los refresh los gestiona Firebase


async def test_downgrade_deja_la_bd_vacia():
    async with motor.begin() as conexion:
        await conexion.run_sync(lambda c: command.upgrade(_alembic(c), "head"))
        await conexion.run_sync(lambda c: command.downgrade(_alembic(c), "base"))
        tablas = await conexion.run_sync(lambda c: set(inspect(c).get_table_names()))
    assert tablas <= {"alembic_version"}
