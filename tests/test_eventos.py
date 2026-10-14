import asyncio

import pytest

from app.config import obtener_configuracion
from app.tiempo_real import Difusor

TOKEN = "token-de-ingesta-de-pruebas-con-32-caracteres-o-mas"

EVENTO = {
    "origen_ip": "203.0.113.7",
    "tipo": "sondeo_rutas",
    "severidad": "media",
    "metodo": "get",
    "ruta": "/admin",
    "agente": "Mozilla/5.0",
}


@pytest.fixture
def ingesta(monkeypatch):
    monkeypatch.setattr(obtener_configuracion(), "ingesta_token", TOKEN)
    return {"X-Ingesta-Token": TOKEN}


async def _ingestar(cliente, cab, *eventos):
    r = await cliente.post("/eventos", json={"eventos": list(eventos)}, headers=cab)
    assert r.status_code == 202, r.text
    return r.json()


# --- Ingesta ---


async def test_ingesta_desactivada_sin_token_configurado(cliente):
    r = await cliente.post("/eventos", json={"eventos": [EVENTO]}, headers={"X-Ingesta-Token": "x"})
    assert r.status_code == 403


async def test_ingesta_con_token_incorrecto_401(cliente, ingesta):
    r = await cliente.post(
        "/eventos", json={"eventos": [EVENTO]}, headers={"X-Ingesta-Token": "otro" * 10}
    )
    assert r.status_code == 401


async def test_ingesta_sin_cabecera_401(cliente, ingesta):
    r = await cliente.post("/eventos", json={"eventos": [EVENTO]})
    assert r.status_code == 401


async def test_ingesta_no_acepta_el_jwt_de_un_admin(cliente, actores, ingesta):
    """La ingesta es de servicio a servicio: ni siquiera un admin puede inyectar eventos."""
    r = await cliente.post("/eventos", json={"eventos": [EVENTO]}, headers=actores.cab["admin"])
    assert r.status_code == 401


async def test_ingesta_correcta(cliente, actores, ingesta):
    assert (await _ingestar(cliente, ingesta, EVENTO, EVENTO))["recibidos"] == 2
    r = await cliente.get("/eventos", headers=actores.cab["admin"])
    assert r.json()["total"] == 2
    assert r.json()["elementos"][0]["metodo"] == "GET"


async def test_ingesta_limpia_y_trunca_lo_que_viene_de_internet(cliente, actores, ingesta):
    largo = {**EVENTO, "ruta": "/" + "a" * 3000, "agente": "linea1\nlinea2\x00"}
    await _ingestar(cliente, ingesta, largo)
    evento = (await cliente.get("/eventos", headers=actores.cab["admin"])).json()["elementos"][0]
    assert len(evento["ruta"]) == 512
    assert evento["agente"] == "linea1linea2"


async def test_ingesta_rechaza_ip_invalida(cliente, ingesta):
    r = await cliente.post(
        "/eventos", json={"eventos": [{**EVENTO, "origen_ip": "no-es-ip"}]}, headers=ingesta
    )
    assert r.status_code == 422


async def test_ingesta_limita_el_lote(cliente, ingesta):
    r = await cliente.post("/eventos", json={"eventos": [EVENTO] * 101}, headers=ingesta)
    assert r.status_code == 422


# --- Consulta (solo admin) ---


@pytest.mark.parametrize("ruta", ["/eventos", "/eventos/resumen"])
async def test_consulta_solo_admin(cliente, actores, ruta):
    for rol in ("usuario", "analista"):
        r = await cliente.get(ruta, headers=actores.cab[rol])
        assert r.status_code == 403


async def test_stream_exige_admin(cliente, actores):
    assert (await cliente.get("/eventos/stream")).status_code == 401
    r = await cliente.get("/eventos/stream", headers=actores.cab["analista"])
    assert r.status_code == 403


async def test_filtros(cliente, actores, ingesta):
    await _ingestar(
        cliente,
        ingesta,
        EVENTO,
        {**EVENTO, "tipo": "fuerza_bruta", "severidad": "alta", "origen_ip": "198.51.100.4"},
    )
    cab = actores.cab["admin"]
    assert (await cliente.get("/eventos?tipo=fuerza_bruta", headers=cab)).json()["total"] == 1
    assert (await cliente.get("/eventos?severidad=media", headers=cab)).json()["total"] == 1
    r = await cliente.get("/eventos?origen_ip=198.51.100.4", headers=cab)
    assert r.json()["total"] == 1


async def test_resumen(cliente, actores, ingesta):
    await _ingestar(
        cliente,
        ingesta,
        EVENTO,
        EVENTO,
        {**EVENTO, "severidad": "critica", "origen_ip": "198.51.100.4", "tipo": "inyeccion"},
    )
    r = await cliente.get("/eventos/resumen", headers=actores.cab["admin"])
    assert r.status_code == 200
    datos = r.json()
    assert datos["total"] == 3
    assert datos["ultima_hora"] == 3
    assert datos["ips_unicas"] == 2
    assert datos["criticos"] == 1
    assert datos["top_ips"][0] == {"clave": "203.0.113.7", "total": 2}
    assert len(datos["por_minuto"]) == 60
    assert len(datos["por_hora"]) == 168
    assert sum(t["total"] for t in datos["por_minuto"]) == 3
    assert datos["por_minuto"][-1]["total"] == 3


# --- Incidencia desde un evento ---


async def test_crear_incidencia_desde_evento(cliente, actores, ingesta):
    await _ingestar(cliente, ingesta, {**EVENTO, "tipo": "fuerza_bruta", "severidad": "alta"})
    cab = actores.cab["admin"]
    evento = (await cliente.get("/eventos", headers=cab)).json()["elementos"][0]

    r = await cliente.post(f"/eventos/{evento['id']}/incidente", headers=cab)
    assert r.status_code == 201
    incidente = r.json()
    assert incidente["severidad"] == "alta"
    assert incidente["categoria"] == "acceso_no_autorizado"
    assert "203.0.113.7" in incidente["titulo"]

    vinculado = (await cliente.get("/eventos", headers=cab)).json()["elementos"][0]
    assert vinculado["incidente_id"] == incidente["id"]

    # Dos veces el mismo evento: conflicto, no una segunda incidencia
    r = await cliente.post(f"/eventos/{evento['id']}/incidente", headers=cab)
    assert r.status_code == 409


async def test_crear_incidencia_solo_admin(cliente, actores, ingesta):
    await _ingestar(cliente, ingesta, EVENTO)
    evento = (await cliente.get("/eventos", headers=actores.cab["admin"])).json()["elementos"][0]
    r = await cliente.post(f"/eventos/{evento['id']}/incidente", headers=actores.cab["analista"])
    assert r.status_code == 403


async def test_crear_incidencia_evento_inexistente(cliente, actores):
    r = await cliente.post("/eventos/999/incidente", headers=actores.cab["admin"])
    assert r.status_code == 404


# --- Difusión en tiempo real ---


async def test_difusor_reparte_a_todos_y_no_bloquea():
    difusor = Difusor(capacidad=2)
    a, b = difusor.suscribir(), difusor.suscribir()
    for n in range(3):  # el tercero desborda la cola: se pierde sin bloquear
        difusor.publicar(str(n))
    assert [a.get_nowait(), a.get_nowait()] == ["0", "1"]
    assert b.qsize() == 2
    difusor.baja(a)
    assert difusor.suscriptores == 1
    await asyncio.sleep(0)
