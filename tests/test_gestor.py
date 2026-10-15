"""El gestor: responsable de una empresa cliente. Ve todo lo de SU empresa y gestiona a sus
trabajadores. Lo importante es lo que NO puede: asomarse a otra empresa, tocar a otro gestor,
ver notas internas del MSSP o hacer el trabajo del analista.
"""

from dataclasses import dataclass

import pytest

from app.db import FabricaSesion
from app.limitador import limitador
from app.modelos import EventoSeguridad, Incidente, Rol, Severidad, TipoEvento, Usuario
from app.servicios import incidentes as servicio_incidentes
from tests.conftest import (
    CONTRASENA,
    cabeceras,
    crear_empresa,
    crear_incidente,
    crear_usuario,
    login,
)


@dataclass
class Gestores:
    cab: dict
    ids: dict
    otra_empresa_id: int


@pytest.fixture
async def gestores(cliente, actores) -> Gestores:
    """Un gestor de la empresa de `actores` (la de usuario y otro), otro gestor de la misma
    empresa, y una segunda empresa con su propio trabajador."""
    otra = await crear_empresa("otra-empresa", "Otra empresa")
    ids = {
        "gestor": await crear_usuario("gestor@test.com", Rol.gestor, actores.empresa.id),
        "gestor2": await crear_usuario("gestor2@test.com", Rol.gestor, actores.empresa.id),
        "ajeno": await crear_usuario("ajeno@test.com", Rol.usuario, otra.id),
    }
    cab = {
        "gestor": await cabeceras(cliente, "gestor@test.com"),
        "ajeno": await cabeceras(cliente, "ajeno@test.com"),
    }
    limitador.reset()
    return Gestores(cab, ids, otra.id)


# --- Incidencias ---


async def test_gestor_ve_todas_las_incidencias_de_su_empresa(cliente, actores, gestores):
    de_usuario = await crear_incidente(cliente, actores.cab["usuario"])
    de_otro = await crear_incidente(cliente, actores.cab["otro"])
    ajena = await crear_incidente(cliente, gestores.cab["ajeno"])

    r = await cliente.get("/incidentes", headers=gestores.cab["gestor"])
    ids = {i["id"] for i in r.json()["elementos"]}
    assert ids == {de_usuario["id"], de_otro["id"]}
    assert ajena["id"] not in ids


async def test_gestor_no_ve_la_incidencia_de_otra_empresa_ni_forzando(cliente, gestores):
    ajena = await crear_incidente(cliente, gestores.cab["ajeno"])
    cab = gestores.cab["gestor"]
    assert (await cliente.get(f"/incidentes/{ajena['id']}", headers=cab)).status_code == 404
    # Ni pidiendo el filtro de la otra empresa: se le fuerza la suya
    r = await cliente.get(f"/incidentes?empresa_id={gestores.otra_empresa_id}", headers=cab)
    assert r.json()["total"] == 0


async def test_gestor_no_ve_notas_internas_del_mssp(cliente, actores, gestores):
    incidente = await crear_incidente(cliente, actores.cab["usuario"])
    await cliente.patch(
        f"/incidentes/{incidente['id']}/notas",
        json={"notas_internas": "Sospechamos de un proveedor"},
        headers=actores.cab["admin"],
    )
    r = await cliente.get(f"/incidentes/{incidente['id']}", headers=gestores.cab["gestor"])
    assert r.status_code == 200
    assert "notas_internas" not in r.json()


async def test_gestor_no_hace_el_trabajo_del_mssp(cliente, actores, gestores):
    incidente = await crear_incidente(cliente, actores.cab["usuario"])
    cab = gestores.cab["gestor"]
    base = f"/incidentes/{incidente['id']}"
    assert (
        await cliente.patch(f"{base}/estado", json={"estado": "en_analisis"}, headers=cab)
    ).status_code == 403
    assert (
        await cliente.patch(
            f"{base}/asignar", json={"analista_id": actores.ids["analista"]}, headers=cab
        )
    ).status_code == 403
    assert (
        await cliente.patch(f"{base}/notas", json={"notas_internas": "x"}, headers=cab)
    ).status_code == 403
    # Tampoco reescribe el reporte de un trabajador: es evidencia
    assert (
        await cliente.patch(base, json={"titulo": "Otro título"}, headers=cab)
    ).status_code == 403


async def test_gestor_reporta_sus_propias_incidencias(cliente, actores, gestores):
    incidente = await crear_incidente(cliente, gestores.cab["gestor"])
    assert incidente["empresa_id"] == actores.empresa.id


# --- Mi empresa ---


async def test_gestor_ve_su_empresa_con_el_codigo(cliente, actores, gestores):
    r = await cliente.get("/mi-empresa", headers=gestores.cab["gestor"])
    assert r.status_code == 200
    assert r.json()["id"] == actores.empresa.id
    assert r.json()["codigo_invitacion"] == actores.empresa.codigo_invitacion


async def test_gestor_regenera_el_codigo_y_queda_auditado(cliente, actores, gestores):
    r = await cliente.post("/mi-empresa/codigo", headers=gestores.cab["gestor"])
    assert r.status_code == 200
    assert r.json()["codigo_invitacion"] != actores.empresa.codigo_invitacion
    r = await cliente.get(
        "/auditoria?accion=regenerar_codigo_invitacion", headers=actores.cab["admin"]
    )
    assert r.json()["total"] == 1


async def test_gestor_lista_solo_a_los_de_su_empresa(cliente, actores, gestores):
    r = await cliente.get("/mi-empresa/usuarios", headers=gestores.cab["gestor"])
    emails = {u["email"] for u in r.json()["elementos"]}
    assert emails == {"usuario@test.com", "otro@test.com", "gestor@test.com", "gestor2@test.com"}


async def test_solo_el_gestor_entra_en_mi_empresa(cliente, actores, gestores):
    # Ni un trabajador, ni el admin (el admin tiene /empresas): /mi-empresa es del gestor
    for quien in ("usuario", "admin", "analista"):
        r = await cliente.get("/mi-empresa", headers=actores.cab[quien])
        assert r.status_code == 403, quien


# --- Gestión de trabajadores ---


async def test_gestor_desactiva_y_reactiva_a_un_trabajador_suyo(cliente, actores, gestores):
    url = f"/mi-empresa/usuarios/{actores.ids['otro']}/activo"
    r = await cliente.patch(url, json={"activo": False}, headers=gestores.cab["gestor"])
    assert r.status_code == 200
    assert (await cliente.get("/usuarios/yo", headers=actores.cab["otro"])).status_code == 401
    r = await cliente.patch(url, json={"activo": True}, headers=gestores.cab["gestor"])
    assert r.json()["activo"] is True


async def test_gestor_restablece_la_contrasena_y_cierra_sus_sesiones(cliente, actores, gestores):
    r = await cliente.patch(
        f"/mi-empresa/usuarios/{actores.ids['otro']}/contrasena",
        json={"contrasena_nueva": "restablecida-por-gestor-1"},
        headers=gestores.cab["gestor"],
    )
    assert r.status_code == 204
    assert (await cliente.get("/usuarios/yo", headers=actores.cab["otro"])).status_code == 401
    r = await cliente.post(
        "/auth/login", json={"email": "otro@test.com", "contrasena": "restablecida-por-gestor-1"}
    )
    assert r.status_code == 200


@pytest.mark.parametrize("victima", ["ajeno", "gestor2", "admin", "analista"])
async def test_gestor_no_toca_a_nadie_fuera_de_sus_trabajadores(
    cliente, actores, gestores, victima
):
    """Ni a un trabajador de otra empresa, ni a otro gestor (sería tomar el control de la
    empresa), ni al personal del MSSP. 404: no confirma siquiera que existan."""
    victima_id = gestores.ids.get(victima) or actores.ids[victima]
    cab = gestores.cab["gestor"]
    r = await cliente.patch(
        f"/mi-empresa/usuarios/{victima_id}/activo", json={"activo": False}, headers=cab
    )
    assert r.status_code == 404
    r = await cliente.patch(
        f"/mi-empresa/usuarios/{victima_id}/contrasena",
        json={"contrasena_nueva": "toma-de-cuenta-12345"},
        headers=cab,
    )
    assert r.status_code == 404


async def test_gestor_no_se_desactiva_a_si_mismo(cliente, gestores):
    r = await cliente.patch(
        f"/mi-empresa/usuarios/{gestores.ids['gestor']}/activo",
        json={"activo": False},
        headers=gestores.cab["gestor"],
    )
    assert r.status_code == 409


async def test_gestor_no_usa_las_rutas_del_admin(cliente, actores, gestores):
    cab = gestores.cab["gestor"]
    assert (await cliente.get("/usuarios", headers=cab)).status_code == 403
    r = await cliente.patch(
        f"/usuarios/{actores.ids['otro']}/rol", json={"rol": "gestor"}, headers=cab
    )
    assert r.status_code == 403
    assert (await cliente.get("/empresas", headers=cab)).status_code == 403


# --- Sensores ---


async def test_gestor_ve_solo_los_sensores_de_su_empresa(cliente, actores, gestores):
    async with FabricaSesion() as sesion:
        for servicio, empresa_id in (
            ("senuelo-propio", actores.empresa.id),
            ("senuelo-ajeno", gestores.otra_empresa_id),
        ):
            sesion.add(
                EventoSeguridad(
                    origen_ip="203.0.113.7",
                    tipo=TipoEvento.sondeo_rutas,
                    severidad=Severidad.media,
                    metodo="GET",
                    ruta="/wp-admin",
                    servicio=servicio,
                    empresa_id=empresa_id,
                )
            )
        await sesion.commit()
    r = await cliente.get("/mi-empresa/sensores", headers=gestores.cab["gestor"])
    assert [s["servicio"] for s in r.json()] == ["senuelo-propio"]


# --- Lo que hace el admin con los gestores ---


async def test_admin_da_de_alta_un_gestor_y_asciende_a_un_trabajador(cliente, actores):
    adm = actores.cab["admin"]
    r = await cliente.post(
        "/usuarios",
        json={
            "email": "nuevo-gestor@test.com",
            "contrasena": CONTRASENA,
            "rol": "gestor",
            "empresa_id": actores.empresa.id,
        },
        headers=adm,
    )
    assert r.status_code == 201
    r = await cliente.patch(
        f"/usuarios/{actores.ids['otro']}/rol", json={"rol": "gestor"}, headers=adm
    )
    assert r.status_code == 200
    # Mismo token del trabajador: ya entra como gestor
    assert (await cliente.get("/mi-empresa", headers=actores.cab["otro"])).status_code == 200
    await login(cliente, "nuevo-gestor@test.com")


# --- Segunda barrera: el servicio, sin la dependencia delante ---


async def test_sin_la_dependencia_un_gestor_sin_empresa_tampoco_ve_nada(cliente, actores):
    """Si un día alguien olvidara poner `UsuarioOperativo` en una ruta nueva, un gestor sin
    empresa no debe heredar la visión del MSSP. Se llama al servicio directamente."""
    incidente = await crear_incidente(cliente, actores.cab["usuario"])
    async with FabricaSesion() as sesion:
        colgado = Usuario(id=999, email="x@test.com", rol=Rol.gestor, empresa_id=None)
        total, elementos = await servicio_incidentes.listar(
            sesion,
            colgado,
            estado=None,
            severidad=None,
            categoria=None,
            limite=100,
            desplazamiento=0,
        )
        assert (total, elementos) == (0, [])
        guardado = await sesion.get(Incidente, incidente["id"])
        assert servicio_incidentes.puede_ver(colgado, guardado) is False
