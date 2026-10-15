"""Autenticación con Firebase: la API verifica el ID token y decide con SU base de datos."""

from app.config import Configuracion
from tests.conftest import CONTRASENA, cabeceras, crear_usuario


async def test_sin_token_401(cliente):
    assert (await cliente.get("/usuarios/yo")).status_code == 401


async def test_token_inventado_401(cliente):
    r = await cliente.get("/usuarios/yo", headers={"Authorization": "Bearer no-es-un-token"})
    assert r.status_code == 401


async def test_uid_valido_pero_desconocido_401(cliente, falsa):
    """Alguien que se registra solo en Firebase (la API key es pública) no entra: su uid no
    está en nuestra base de datos."""
    await falsa.crear("intruso@test.com", CONTRASENA)
    token = falsa.iniciar_sesion("intruso@test.com", CONTRASENA)
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_token_revocado_401(cliente, falsa):
    await crear_usuario("u@test.com")
    cab = await cabeceras(cliente, "u@test.com")
    await falsa.revocar(await falsa.buscar("u@test.com"))
    assert (await cliente.get("/usuarios/yo", headers=cab)).status_code == 401


async def test_el_rol_sale_de_la_bd_no_del_token(cliente, actores):
    r = await cliente.get("/usuarios/yo", headers=actores.cab["analista"])
    assert r.json()["rol"] == "analista"


async def test_entrada_y_salida_quedan_auditadas(cliente, actores):
    await cliente.post("/auth/salida", headers=actores.cab["usuario"])
    adm = actores.cab["admin"]
    entradas = (await cliente.get("/auditoria?accion=login", headers=adm)).json()["total"]
    salidas = (await cliente.get("/auditoria?accion=logout", headers=adm)).json()["total"]
    assert entradas == len(actores.ids)
    assert salidas == 1


async def test_config_cliente_es_publica_y_sin_secretos(cliente, monkeypatch):
    from app.config import obtener_configuracion

    config = obtener_configuracion()
    monkeypatch.setattr(config, "firebase_api_key", "clave-web")
    monkeypatch.setattr(config, "firebase_project_id", "proyecto")
    monkeypatch.setattr(config, "firebase_credenciales", "SECRETO-QUE-NO-DEBE-SALIR")
    r = await cliente.get("/config/cliente")
    assert r.status_code == 200
    assert r.json()["firebase"]["apiKey"] == "clave-web"
    assert "SECRETO" not in r.text


def test_produccion_sin_firebase_no_arranca(monkeypatch):
    import pytest
    from pydantic import ValidationError

    monkeypatch.setenv("ENTORNO", "produccion")
    for var in ("FIREBASE_CREDENCIALES", "FIREBASE_API_KEY", "FIREBASE_PROJECT_ID"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ValidationError):
        Configuracion(_env_file=None)
