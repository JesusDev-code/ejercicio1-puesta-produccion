from sqlalchemy import func, select

from app.db import FabricaSesion
from app.demo import EMPRESAS, INCIDENTES, USUARIOS, sembrar_demo
from app.modelos import Empresa, Incidente, Rol, Usuario
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


async def test_demo_reparte_usuarios_e_incidencias_entre_clientes():
    async with FabricaSesion() as sesion:
        await sembrar_demo(sesion)
        assert await sesion.scalar(select(func.count(Empresa.id))) == len(EMPRESAS)
        # El personal del MSSP no tiene empresa; los reportantes, sí
        sin_empresa = await sesion.scalars(select(Usuario.rol).where(Usuario.empresa_id.is_(None)))
        assert set(sin_empresa) == {Rol.analista}
        huerfanas = select(func.count(Incidente.id)).where(Incidente.empresa_id.is_(None))
        assert await sesion.scalar(huerfanas) == 0


async def test_demo_completa_empresas_en_una_bd_sembrada_antes():
    """Producción se sembró antes de que existieran las empresas: volver a sembrar las crea
    y reparte a los usuarios de demo, sin duplicar nada."""
    async with FabricaSesion() as sesion:
        await sembrar_demo(sesion)
    async with FabricaSesion() as sesion:
        for u in await sesion.scalars(select(Usuario)):
            u.empresa_id = None
        for i in await sesion.scalars(select(Incidente)):
            i.empresa_id = None
        for e in await sesion.scalars(select(Empresa)):
            await sesion.delete(e)
        await sesion.commit()

    async with FabricaSesion() as sesion:
        assert await sembrar_demo(sesion) is False
    async with FabricaSesion() as sesion:
        assert await sesion.scalar(select(func.count(Empresa.id))) == len(EMPRESAS)
        huerfanas = select(func.count(Incidente.id)).where(Incidente.empresa_id.is_(None))
        assert await sesion.scalar(huerfanas) == 0
