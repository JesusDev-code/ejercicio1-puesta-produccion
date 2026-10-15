"""Flujo de navegador: el refresco va en cookie HttpOnly y nunca aparece en el cuerpo.

httpx no reenvía cookies `Secure` sobre http://test, así que los tests las mandan a mano."""

from app.config import obtener_configuracion
from app.routers.auth import COOKIE_REFRESCO
from tests.conftest import CONTRASENA, crear_usuario

EMAIL = "web@test.com"


def _cookie(respuesta) -> str:
    cabecera = respuesta.headers["set-cookie"]
    nombre_valor = cabecera.split(";", 1)[0]
    nombre, valor = nombre_valor.split("=", 1)
    assert nombre == COOKIE_REFRESCO
    return valor


async def _login_web(cliente):
    await crear_usuario(EMAIL)
    return await cliente.post("/auth/web/login", json={"email": EMAIL, "contrasena": CONTRASENA})


async def test_login_web_pone_cookie_endurecida_y_no_expone_el_refresco(cliente):
    r = await _login_web(cliente)
    assert r.status_code == 200
    assert "token_refresco" not in r.json()
    assert r.json()["token_acceso"]

    cabecera = r.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=strict", "path=/auth/web", "max-age="):
        assert atributo in cabecera


async def test_login_web_credenciales_malas_sin_cookie(cliente):
    await crear_usuario(EMAIL)
    r = await cliente.post("/auth/web/login", json={"email": EMAIL, "contrasena": "mala"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


async def test_refrescar_web_rota_la_cookie(cliente):
    viejo = _cookie(await _login_web(cliente))
    r = await cliente.post("/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={viejo}"})
    assert r.status_code == 200
    assert "token_refresco" not in r.json()
    nuevo = _cookie(r)
    assert nuevo != viejo


async def test_refrescar_web_sin_cookie_401(cliente):
    r = await cliente.post("/auth/web/refrescar")
    assert r.status_code == 401


async def test_refrescar_web_reutilizada_revoca_la_familia(cliente):
    robada = _cookie(await _login_web(cliente))
    legitima = _cookie(
        await cliente.post("/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={robada}"})
    )
    r = await cliente.post("/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={robada}"})
    assert r.status_code == 401
    r = await cliente.post(
        "/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={legitima}"}
    )
    assert r.status_code == 401


async def test_logout_web_revoca_y_borra_la_cookie(cliente):
    cookie = _cookie(await _login_web(cliente))
    r = await cliente.post("/auth/web/logout", headers={"Cookie": f"{COOKIE_REFRESCO}={cookie}"})
    assert r.status_code == 204
    assert "max-age=0" in r.headers["set-cookie"].lower()

    r = await cliente.post("/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={cookie}"})
    assert r.status_code == 401


async def test_logout_web_sin_cookie_204(cliente):
    r = await cliente.post("/auth/web/logout")
    assert r.status_code == 204


async def test_ruta_de_la_cookie_configurable_tras_un_proxy(cliente, monkeypatch):
    """Traefik publica la API bajo /api: la cookie tiene que llevar el Path que ve el navegador."""
    monkeypatch.setattr(obtener_configuracion(), "cookie_refresco_ruta", "/api/auth/web")
    r = await _login_web(cliente)
    assert "path=/api/auth/web" in r.headers["set-cookie"].lower()
