"""Clientes del MSSP y aislamiento entre ellos: lo de una empresa no se ve desde otra."""

import pytest

from app.config import obtener_configuracion
from app.db import FabricaSesion
from app.limitador import limitador
from app.modelos import Incidente
from tests.conftest import CONTRASENA, cabeceras, crear_incidente
from tests.test_eventos import EVENTO, TOKEN, _ingestar

IBARRA = {"codigo": "transportes-ibarra", "nombre": "Transportes Ibarra", "sector": "Logística"}
SOLANA = {"codigo": "clinica-solana", "nombre": "Clínica Solana", "sector": "Sanidad"}


async def _crear_empresa(cliente, cab, datos) -> int:
    r = await cliente.post("/empresas", json=datos, headers=cab)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _alta(cliente, cab_admin, email, empresa_id, rol="usuario") -> dict:
    r = await cliente.post(
        "/usuarios",
        json={"email": email, "contrasena": CONTRASENA, "rol": rol, "empresa_id": empresa_id},
        headers=cab_admin,
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def ingesta(monkeypatch):
    monkeypatch.setattr(obtener_configuracion(), "ingesta_token", TOKEN)
    return {"X-Ingesta-Token": TOKEN}


class Clientes:
    def __init__(self, ids: dict, cab: dict):
        self.ids = ids
        self.cab = cab


@pytest.fixture
async def clientes(cliente, actores) -> Clientes:
    """Dos empresas con un trabajador cada una, más el personal del MSSP de `actores`."""
    adm = actores.cab["admin"]
    ids = {
        "ibarra": await _crear_empresa(cliente, adm, IBARRA),
        "solana": await _crear_empresa(cliente, adm, SOLANA),
    }
    ids["u_ibarra"] = (await _alta(cliente, adm, "ana@ibarra.es", ids["ibarra"]))["id"]
    ids["u_solana"] = (await _alta(cliente, adm, "luis@solana.es", ids["solana"]))["id"]
    cab = {
        "ibarra": await cabeceras(cliente, "ana@ibarra.es"),
        "solana": await cabeceras(cliente, "luis@solana.es"),
    }
    limitador.reset()
    return Clientes(ids, cab)


# --- Gestión de empresas ---


async def test_crear_y_listar_empresas(cliente, actores, clientes):
    r = await cliente.get("/empresas", headers=actores.cab["admin"])
    assert r.status_code == 200
    assert [e["codigo"] for e in r.json()["elementos"]] == ["clinica-solana", "transportes-ibarra"]


async def test_empresa_duplicada_409(cliente, actores, clientes):
    adm = actores.cab["admin"]
    r = await cliente.post("/empresas", json=IBARRA, headers=adm)
    assert r.status_code == 409
    mismo_nombre = {**IBARRA, "codigo": "otro-codigo", "nombre": "transportes ibarra"}
    assert (await cliente.post("/empresas", json=mismo_nombre, headers=adm)).status_code == 409


@pytest.mark.parametrize("codigo", ["Con Mayusculas", "guion-final-", "a", "con_barra_baja"])
async def test_codigo_de_empresa_invalido_422(cliente, actores, codigo):
    datos = {**IBARRA, "codigo": codigo}
    r = await cliente.post("/empresas", json=datos, headers=actores.cab["admin"])
    assert r.status_code == 422


async def test_editar_empresa_pero_no_su_codigo(cliente, actores, clientes):
    adm, url = actores.cab["admin"], f"/empresas/{clientes.ids['ibarra']}"
    r = await cliente.patch(url, json={"nombre": "Ibarra Logística", "sector": ""}, headers=adm)
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ibarra Logística"
    assert r.json()["sector"] is None
    # El código lo usan los sensores: no es editable
    assert (await cliente.patch(url, json={"codigo": "x"}, headers=adm)).status_code == 422


@pytest.mark.parametrize("quien", ["usuario", "analista"])
async def test_empresas_solo_admin(cliente, actores, clientes, quien):
    cab = actores.cab[quien]
    assert (await cliente.get("/empresas", headers=cab)).status_code == 403
    assert (await cliente.post("/empresas", json=SOLANA, headers=cab)).status_code == 403
    r = await cliente.patch(
        f"/empresas/{clientes.ids['ibarra']}", json={"activa": False}, headers=cab
    )
    assert r.status_code == 403


async def test_empresas_quedan_auditadas(cliente, actores, clientes):
    r = await cliente.get("/auditoria?accion=crear_empresa", headers=actores.cab["admin"])
    assert r.json()["total"] == 2


# --- Miembros de una empresa ---


@pytest.mark.parametrize("rol", ["admin", "analista"])
async def test_personal_del_mssp_no_tiene_empresa(cliente, actores, clientes, rol):
    r = await cliente.post(
        "/usuarios",
        json={
            "email": "x@ibarra.es",
            "contrasena": CONTRASENA,
            "rol": rol,
            "empresa_id": clientes.ids["ibarra"],
        },
        headers=actores.cab["admin"],
    )
    assert r.status_code == 422


async def test_alta_en_empresa_inexistente_422(cliente, actores):
    r = await cliente.post(
        "/usuarios",
        json={"email": "x@nadie.es", "contrasena": CONTRASENA, "empresa_id": 999},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 422


async def test_usuario_de_cliente_no_asciende_a_analista(cliente, actores, clientes):
    r = await cliente.patch(
        f"/usuarios/{clientes.ids['u_ibarra']}/rol",
        json={"rol": "analista"},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 409


async def test_filtrar_usuarios_por_empresa(cliente, actores, clientes):
    r = await cliente.get(
        f"/usuarios?empresa_id={clientes.ids['solana']}", headers=actores.cab["admin"]
    )
    assert [u["email"] for u in r.json()["elementos"]] == ["luis@solana.es"]


async def test_yo_incluye_la_empresa(cliente, clientes):
    r = await cliente.get("/usuarios/yo", headers=clientes.cab["ibarra"])
    assert r.json()["empresa_id"] == clientes.ids["ibarra"]


# --- Aislamiento de incidencias ---


async def test_la_incidencia_hereda_la_empresa_del_reportante(cliente, clientes):
    inc = await crear_incidente(cliente, clientes.cab["ibarra"])
    assert inc["empresa_id"] == clientes.ids["ibarra"]


async def test_ibarra_no_lee_ni_edita_ni_lista_lo_de_solana(cliente, clientes):
    inc = await crear_incidente(cliente, clientes.cab["solana"])
    cab, url = clientes.cab["ibarra"], f"/incidentes/{inc['id']}"

    assert (await cliente.get(url, headers=cab)).status_code == 404
    assert (await cliente.patch(url, json={"titulo": "Mío"}, headers=cab)).status_code == 404
    r = await cliente.patch(f"{url}/estado", json={"estado": "en_analisis"}, headers=cab)
    assert r.status_code == 404
    assert (
        await cliente.patch(f"{url}/notas", json={"notas_internas": "x"}, headers=cab)
    ).status_code == 404

    # Pedir la empresa ajena en el filtro no sirve: al cliente se le fija la suya
    r = await cliente.get(f"/incidentes?empresa_id={clientes.ids['solana']}", headers=cab)
    assert r.json()["total"] == 0


async def test_el_aislamiento_no_depende_solo_del_reportante(cliente, clientes):
    """Defensa en profundidad: aunque un dato inconsistente hiciera a Ibarra «reportante» de
    una incidencia de Solana, la comprobación de empresa la sigue ocultando."""
    inc = await crear_incidente(cliente, clientes.cab["solana"])
    async with FabricaSesion() as sesion:
        fila = await sesion.get(Incidente, inc["id"])
        fila.reportante_id = clientes.ids["u_ibarra"]
        await sesion.commit()
    r = await cliente.get(f"/incidentes/{inc['id']}", headers=clientes.cab["ibarra"])
    assert r.status_code == 404


async def test_admin_filtra_incidencias_por_empresa(cliente, actores, clientes):
    await crear_incidente(cliente, clientes.cab["ibarra"])
    await crear_incidente(cliente, clientes.cab["solana"])
    await crear_incidente(cliente, actores.cab["usuario"])  # personal del MSSP, sin empresa
    adm = actores.cab["admin"]
    assert (await cliente.get("/incidentes", headers=adm)).json()["total"] == 3
    r = await cliente.get(f"/incidentes?empresa_id={clientes.ids['ibarra']}", headers=adm)
    assert [i["empresa_id"] for i in r.json()["elementos"]] == [clientes.ids["ibarra"]]


async def test_no_se_asigna_un_usuario_de_cliente_como_analista(cliente, actores, clientes):
    inc = await crear_incidente(cliente, clientes.cab["ibarra"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}/asignar",
        json={"analista_id": clientes.ids["u_ibarra"]},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 422


# --- Baja de un cliente ---


async def test_desactivar_empresa_deja_fuera_a_sus_usuarios(cliente, actores, clientes):
    r = await cliente.patch(
        f"/empresas/{clientes.ids['ibarra']}", json={"activa": False}, headers=actores.cab["admin"]
    )
    assert r.status_code == 200
    # El token que ya tenía deja de valer al momento, y no puede volver a entrar
    assert (await cliente.get("/usuarios/yo", headers=clientes.cab["ibarra"])).status_code == 401
    r = await cliente.post("/auth/login", json={"email": "ana@ibarra.es", "contrasena": CONTRASENA})
    assert r.status_code == 401
    # Los demás clientes siguen igual
    assert (await cliente.get("/usuarios/yo", headers=clientes.cab["solana"])).status_code == 200


async def test_no_se_dan_altas_en_una_empresa_desactivada(cliente, actores, clientes):
    adm = actores.cab["admin"]
    await cliente.patch(f"/empresas/{clientes.ids['ibarra']}", json={"activa": False}, headers=adm)
    r = await cliente.post(
        "/usuarios",
        json={
            "email": "nuevo@ibarra.es",
            "contrasena": CONTRASENA,
            "empresa_id": clientes.ids["ibarra"],
        },
        headers=adm,
    )
    assert r.status_code == 422


# --- Eventos por cliente ---


async def test_ingesta_asigna_la_empresa_del_sensor(cliente, actores, clientes, ingesta):
    await _ingestar(cliente, ingesta, {**EVENTO, "empresa": "clinica-solana"}, EVENTO)
    r = await cliente.get("/eventos", headers=actores.cab["admin"])
    assert sorted(e["empresa_id"] or 0 for e in r.json()["elementos"]) == [
        0,
        clientes.ids["solana"],
    ]


async def test_ingesta_con_empresa_desconocida_rechaza_el_lote(cliente, ingesta):
    r = await cliente.post(
        "/eventos", json={"eventos": [{**EVENTO, "empresa": "no-existe"}]}, headers=ingesta
    )
    assert r.status_code == 422
    assert "no-existe" in r.json()["detail"]


async def test_eventos_y_resumen_filtrados_por_empresa(cliente, actores, clientes, ingesta):
    await _ingestar(
        cliente,
        ingesta,
        {**EVENTO, "empresa": "clinica-solana"},
        {**EVENTO, "empresa": "clinica-solana", "severidad": "critica"},
        {**EVENTO, "empresa": "transportes-ibarra"},
    )
    adm, solana = actores.cab["admin"], clientes.ids["solana"]
    r = await cliente.get(f"/eventos?empresa_id={solana}", headers=adm)
    assert r.json()["total"] == 2

    resumen = (await cliente.get(f"/eventos/resumen?empresa_id={solana}", headers=adm)).json()
    assert resumen["total"] == 2
    assert resumen["criticos"] == 1
    assert sum(t["total"] for t in resumen["por_minuto"]) == 2
    assert (await cliente.get("/eventos/resumen", headers=adm)).json()["total"] == 3


async def test_incidencia_desde_evento_es_del_cliente_del_sensor(
    cliente, actores, clientes, ingesta
):
    await _ingestar(cliente, ingesta, {**EVENTO, "empresa": "transportes-ibarra"})
    adm = actores.cab["admin"]
    evento = (await cliente.get("/eventos", headers=adm)).json()["elementos"][0]
    r = await cliente.post(f"/eventos/{evento['id']}/incidente", headers=adm)
    assert r.status_code == 201
    assert r.json()["empresa_id"] == clientes.ids["ibarra"]


async def test_sensores_por_servicio_y_empresa(cliente, actores, clientes, ingesta):
    await _ingestar(
        cliente,
        ingesta,
        {**EVENTO, "empresa": "clinica-solana"},
        {**EVENTO, "empresa": "clinica-solana"},
        {**EVENTO, "servicio": "generador-demo", "empresa": "transportes-ibarra"},
    )
    r = await cliente.get("/eventos/sensores", headers=actores.cab["admin"])
    assert r.status_code == 200
    vistos = {(s["servicio"], s["empresa_id"]): s for s in r.json()}
    solana = vistos[("senuelo", clientes.ids["solana"])]
    assert solana["total"] == 2
    assert solana["ultimas_24h"] == 2
    assert vistos[("generador-demo", clientes.ids["ibarra"])]["total"] == 1


async def test_sensores_solo_admin(cliente, actores, clientes):
    r = await cliente.get("/eventos/sensores", headers=clientes.cab["ibarra"])
    assert r.status_code == 403
