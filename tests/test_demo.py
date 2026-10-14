from sqlalchemy import func, select

from app.db import FabricaSesion
from app.demo import INCIDENTES, USUARIOS, sembrar_demo
from app.modelos import Incidente, Rol, Usuario
from tests.conftest import cabeceras, crear_usuario


async def test_sembrar_demo_es_idempotente():
    async with FabricaSesion() as sesion:
        assert await sembrar_demo(sesion) is True
    async with FabricaSesion() as sesion:
        assert await sembrar_demo(sesion) is False
        assert await sesion.scalar(select(func.count(Usuario.id))) == len(USUARIOS)
        assert await sesion.scalar(select(func.count(Incidente.id))) == len(INCIDENTES)


async def test_demo_visible_para_admin_y_no_para_un_usuario_nuevo(cliente):
    async with FabricaSesion() as sesion:
        await sembrar_demo(sesion)
    await crear_usuario("admin@test.com", rol=Rol.admin)
    await crear_usuario("nuevo@test.com")

    r = await cliente.get("/incidentes", headers=await cabeceras(cliente, "admin@test.com"))
    assert r.json()["total"] == len(INCIDENTES)
    r = await cliente.get("/incidentes", headers=await cabeceras(cliente, "nuevo@test.com"))
    assert r.json()["total"] == 0

    r = await cliente.get("/auditoria", headers=await cabeceras(cliente, "admin@test.com"))
    assert r.status_code == 200 and r.json()["total"] > len(INCIDENTES)
