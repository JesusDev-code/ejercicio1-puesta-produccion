"""Login con Google y GitHub. La red del proveedor se sustituye por `obtener_perfil` falso: lo que
se prueba es la parte de Umbral (state, PKCE, cookies, vinculación y sesión)."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest

from app.config import obtener_configuracion
from app.modelos import ahora
from app.routers.auth import COOKIE_OAUTH, COOKIE_REFRESCO
from app.seguridad import (
    crear_estado_oauth,
    crear_token_acceso,
    decodificar_token_acceso,
    reto_pkce,
)
from app.servicios import mfa
from app.servicios import oauth as servicio_oauth
from app.servicios.oauth import PerfilExterno, perfil_github, perfil_google
from tests.conftest import CONTRASENA, cabeceras, crear_usuario

WEB = "https://umbral.ejemplo.com"
PERFIL = PerfilExterno(sujeto="g-123", email="nueva@gmail.com", verificado=True)


@pytest.fixture
def proveedores(monkeypatch):
    config = obtener_configuracion()
    for campo, valor in {
        "url_publica": WEB,
        "google_client_id": "id-google",
        "google_client_secret": "secreto-google",
        "github_client_id": "id-github",
        "github_client_secret": "secreto-github",
    }.items():
        monkeypatch.setattr(config, campo, valor)


@pytest.fixture
def perfil(monkeypatch):
    """El perfil que «devolverá» el proveedor. Se cambia con `perfil.actual = ...`."""

    class Falso:
        actual = PERFIL
        llamadas = 0

    falso = Falso()

    async def obtener(_proveedor, _codigo, _verificador):
        falso.llamadas += 1
        return falso.actual

    monkeypatch.setattr(servicio_oauth, "obtener_perfil", obtener)
    return falso


def _cookies(respuesta) -> dict[str, str]:
    """httpx no reenvía cookies Secure sobre http://test: se leen y se mandan a mano."""
    cookies = {}
    for cabecera in respuesta.headers.get_list("set-cookie"):
        nombre, valor = cabecera.split(";", 1)[0].split("=", 1)
        cookies[nombre] = valor
    return cookies


async def _ida(cliente, proveedor: str = "google") -> tuple[str, str]:
    """(cookie del flujo, state) tras pulsar el botón."""
    r = await cliente.get(f"/auth/oauth/{proveedor}/inicio")
    assert r.status_code == 302
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return _cookies(r)[COOKIE_OAUTH], state


async def _vuelta(cliente, cookie: str, state: str, proveedor: str = "google"):
    return await cliente.get(
        f"/auth/oauth/{proveedor}/callback",
        params={"code": "codigo-del-proveedor", "state": state},
        headers={"Cookie": f"{COOKIE_OAUTH}={cookie}"},
    )


async def _yo_con_refresco(cliente, refresco: str) -> dict:
    r = await cliente.post(
        "/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={refresco}"}
    )
    assert r.status_code == 200, r.text
    cab = {"Authorization": f"Bearer {r.json()['token_acceso']}"}
    return (await cliente.get("/usuarios/yo", headers=cab)).json()


def test_reto_pkce_vector_de_la_rfc_7636():
    verificador = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    assert reto_pkce(verificador) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_perfil_github_solo_acepta_el_principal_verificado():
    usuario = {"id": 42}
    emails = [
        {"email": "secundario@x.com", "primary": False, "verified": True},
        {"email": "principal@x.com", "primary": True, "verified": True},
    ]
    assert perfil_github(usuario, emails) == PerfilExterno("42", "principal@x.com", True)
    sin_verificar = [{"email": "principal@x.com", "primary": True, "verified": False}]
    assert perfil_github(usuario, sin_verificar).verificado is False


def test_perfil_google_exige_email_verified_booleano():
    assert perfil_google({"sub": "1", "email": "a@b.com", "email_verified": True}).verificado
    assert not perfil_google({"sub": "1", "email": "a@b.com", "email_verified": "true"}).verificado


async def test_sin_configuracion_no_hay_proveedores(cliente):
    assert (await cliente.get("/auth/oauth/proveedores")).json() == {"proveedores": []}
    r = await cliente.get("/auth/oauth/google/inicio")
    assert r.status_code == 302
    assert r.headers["location"].endswith("/login?error=oauth")


async def test_inicio_manda_al_proveedor_con_pkce_y_cookie_lax(cliente, proveedores):
    assert (await cliente.get("/auth/oauth/proveedores")).json() == {
        "proveedores": ["google", "github"]
    }
    r = await cliente.get("/auth/oauth/google/inicio")
    destino = urlparse(r.headers["location"])
    params = parse_qs(destino.query)
    assert destino.netloc == "accounts.google.com"
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == [f"{WEB}/auth/oauth/google/callback"]
    assert len(params["state"][0]) >= 40

    cabecera = r.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=lax", "path=/auth/oauth", "max-age=600"):
        assert atributo in cabecera


async def test_primer_login_crea_cuenta_pendiente_sin_contrasena(cliente, proveedores, perfil):
    cookie, state = await _ida(cliente)
    r = await _vuelta(cliente, cookie, state)
    assert r.status_code == 302
    assert r.headers["location"] == f"{WEB}/"

    cookies = _cookies(r)
    assert cookies[COOKIE_OAUTH] == '""'  # la cookie del flujo se borra: un solo uso
    yo = await _yo_con_refresco(cliente, cookies[COOKIE_REFRESCO])
    assert yo["email"] == "nueva@gmail.com"
    assert yo["rol"] == "usuario" and yo["pendiente"] is True
    assert yo["tiene_contrasena"] is False
    assert yo["proveedores"] == ["google"]

    # Sin contraseña no se puede entrar con contraseña, ni con "!" ni con nada
    r = await cliente.post("/auth/login", json={"email": "nueva@gmail.com", "contrasena": "!"})
    assert r.status_code == 401


async def test_la_identidad_se_busca_por_sujeto_no_por_email(cliente, proveedores, perfil):
    cookie, state = await _ida(cliente)
    primero = await _yo_con_refresco(
        cliente, _cookies(await _vuelta(cliente, cookie, state))[COOKIE_REFRESCO]
    )

    # El usuario cambia su email en Google: sigue siendo la misma cuenta de Umbral
    perfil.actual = PerfilExterno(sujeto="g-123", email="otro@gmail.com", verificado=True)
    cookie, state = await _ida(cliente)
    segundo = await _yo_con_refresco(
        cliente, _cookies(await _vuelta(cliente, cookie, state))[COOKIE_REFRESCO]
    )
    assert segundo["id"] == primero["id"]


async def test_state_distinto_es_login_csrf(cliente, proveedores, perfil, actores):
    cookie, _ = await _ida(cliente)
    r = await _vuelta(cliente, cookie, "state-del-atacante")
    assert r.headers["location"] == f"{WEB}/login?error=oauth"
    assert COOKIE_REFRESCO not in _cookies(r)
    assert perfil.llamadas == 0  # ni siquiera se canjea el código

    r = await cliente.get("/auditoria?accion=oauth_estado_invalido", headers=actores.cab["admin"])
    assert r.json()["total"] == 1


async def test_sin_cookie_del_flujo_no_hay_login(cliente, proveedores, perfil):
    _, state = await _ida(cliente)
    r = await cliente.get("/auth/oauth/google/callback", params={"code": "x", "state": state})
    assert r.headers["location"] == f"{WEB}/login?error=oauth"
    assert perfil.llamadas == 0


async def test_cookie_de_otro_proveedor_no_vale(cliente, proveedores, perfil):
    cookie, state = await _ida(cliente, "github")
    r = await _vuelta(cliente, cookie, state, "google")
    assert r.headers["location"] == f"{WEB}/login?error=oauth"


async def test_cookie_falsificada_no_vale(cliente, proveedores, perfil):
    buena = crear_estado_oauth("google", "mi-state", "mi-verificador")
    cabecera, cuerpo, firma = buena.split(".")
    falsa = f"{cabecera}.{cuerpo}.{firma[::-1]}"
    r = await _vuelta(cliente, falsa, "mi-state")
    assert r.headers["location"] == f"{WEB}/login?error=oauth"


async def test_email_no_verificado_no_crea_cuenta(cliente, proveedores, perfil):
    perfil.actual = PerfilExterno(sujeto="g-9", email="victima@gmail.com", verificado=False)
    cookie, state = await _ida(cliente)
    r = await _vuelta(cliente, cookie, state)
    assert r.headers["location"] == f"{WEB}/login?error=oauth"
    await crear_usuario("victima@gmail.com")  # el email sigue libre: no se creó nada


async def test_no_se_vincula_solo_a_una_cuenta_existente(cliente, proveedores, perfil):
    """Pre-account hijacking: el atacante registra antes el email de la víctima con SU
    contraseña. Si Google vinculase solo por email, compartirían cuenta."""
    await crear_usuario("nueva@gmail.com")  # la cuenta «del atacante»
    cookie, state = await _ida(cliente)
    r = await _vuelta(cliente, cookie, state)
    assert r.headers["location"] == f"{WEB}/login?error=oauth_email"
    assert COOKIE_REFRESCO not in _cookies(r)

    cab = await cabeceras(cliente, "nueva@gmail.com")
    assert (await cliente.get("/usuarios/yo", headers=cab)).json()["proveedores"] == []


async def test_vincular_desde_mi_cuenta(cliente, proveedores, perfil):
    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    perfil.actual = PerfilExterno(sujeto="gh-7", email="yo@personal.com", verificado=True)

    r = await cliente.post(
        "/usuarios/yo/identidades/github", json={"contrasena": CONTRASENA}, headers=cab
    )
    assert r.status_code == 200
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    r = await _vuelta(cliente, _cookies(r)[COOKIE_OAUTH], state, "github")
    assert r.headers["location"] == f"{WEB}/cuenta?vinculado=github"
    assert COOKIE_REFRESCO not in _cookies(r)  # vincular no abre otra sesión

    yo = (await cliente.get("/usuarios/yo", headers=cab)).json()
    assert yo["proveedores"] == ["github"]

    # Desde ahora, GitHub entra en esa cuenta aunque el email sea otro
    cookie, state = await _ida(cliente, "github")
    entrada = _cookies(await _vuelta(cliente, cookie, state, "github"))
    assert (await _yo_con_refresco(cliente, entrada[COOKIE_REFRESCO]))["id"] == yo["id"]


async def test_vincular_exige_la_contrasena(cliente, proveedores):
    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    r = await cliente.post(
        "/usuarios/yo/identidades/github", json={"contrasena": "incorrecta-123"}, headers=cab
    )
    assert r.status_code == 422
    assert COOKIE_OAUTH not in _cookies(r)


async def test_no_se_vincula_una_identidad_de_otro(cliente, proveedores, perfil):
    cookie, state = await _ida(cliente)
    await _vuelta(cliente, cookie, state)  # g-123 ya es de nueva@gmail.com

    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    r = await cliente.post(
        "/usuarios/yo/identidades/google", json={"contrasena": CONTRASENA}, headers=cab
    )
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    r = await _vuelta(cliente, _cookies(r)[COOKIE_OAUTH], state)
    assert r.headers["location"] == f"{WEB}/cuenta?error_vinculo=1"


async def test_vincular_caduca_si_cambia_la_sesion(cliente, proveedores, perfil):
    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    r = await cliente.post(
        "/usuarios/yo/identidades/google", json={"contrasena": CONTRASENA}, headers=cab
    )
    cookie = _cookies(r)[COOKIE_OAUTH]
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    # Cambia la contraseña entre la ida y la vuelta (se cierran sus sesiones)
    await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": CONTRASENA, "contrasena_nueva": "otra-contrasena-larga"},
        headers=cab,
    )
    r = await _vuelta(cliente, cookie, state)
    assert r.headers["location"] == f"{WEB}/cuenta?error_vinculo=1"


async def test_no_se_desvincula_la_unica_forma_de_entrar(cliente, proveedores, perfil):
    cookie, state = await _ida(cliente)
    refresco = _cookies(await _vuelta(cliente, cookie, state))[COOKIE_REFRESCO]
    r = await cliente.post(
        "/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={refresco}"}
    )
    cab = {"Authorization": f"Bearer {r.json()['token_acceso']}"}
    r = await cliente.post("/usuarios/yo/identidades/google/desvincular", json={}, headers=cab)
    assert r.status_code == 409


async def test_oauth_no_se_salta_el_mfa(cliente, proveedores, perfil, monkeypatch):
    monkeypatch.setattr(mfa, "_instante", lambda: 1_800_000_000.0)
    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    r = await cliente.post("/usuarios/yo/mfa/iniciar", json={"contrasena": CONTRASENA}, headers=cab)
    secreto = r.json()["secreto"]
    await cliente.post(
        "/usuarios/yo/mfa/activar",
        json={"codigo": pyotp.TOTP(secreto).at(1_800_000_000)},
        headers=cab,
    )
    r = await cliente.post(
        "/usuarios/yo/identidades/google", json={"contrasena": CONTRASENA}, headers=cab
    )
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    await _vuelta(cliente, _cookies(r)[COOKIE_OAUTH], state)

    cookie, state = await _ida(cliente)
    r = await _vuelta(cliente, cookie, state)
    assert r.headers["location"].startswith(f"{WEB}/login#mfa=")
    assert COOKIE_REFRESCO not in _cookies(r)

    desafio = r.headers["location"].split("#mfa=", 1)[1]
    r = await cliente.post(
        "/auth/web/mfa",
        json={"desafio": desafio, "codigo": pyotp.TOTP(secreto).at(1_800_000_030)},
    )
    assert r.status_code == 200
    assert COOKIE_REFRESCO in _cookies(r)


# --- Reautenticación de las cuentas sin contraseña: falla en cerrado ---


async def _cab_oauth(cliente) -> dict:
    """Sesión recién abierta con Google por una cuenta sin contraseña."""
    cookie, state = await _ida(cliente)
    refresco = _cookies(await _vuelta(cliente, cookie, state))[COOKIE_REFRESCO]
    r = await cliente.post(
        "/auth/web/refrescar", headers={"Cookie": f"{COOKIE_REFRESCO}={refresco}"}
    )
    return {"Authorization": f"Bearer {r.json()['token_acceso']}"}


def _mas_tarde(monkeypatch, minutos: int) -> None:
    """La sesión sigue viva, pero el login fue hace `minutos`."""
    momento = ahora() + timedelta(minutes=minutos)
    monkeypatch.setattr(mfa, "ahora", lambda: momento)


async def test_el_refresco_conserva_la_hora_del_login(cliente, proveedores, perfil):
    cab = await _cab_oauth(cliente)
    datos = decodificar_token_acceso(cab["Authorization"].split()[1])
    assert datos.autenticado_en is not None
    assert abs((ahora() - datos.autenticado_en).total_seconds()) < 60


async def test_sin_contrasena_y_login_reciente_puede_cambiar_como_entra(
    cliente, proveedores, perfil
):
    cab = await _cab_oauth(cliente)
    r = await cliente.post("/usuarios/yo/mfa/iniciar", json={}, headers=cab)
    assert r.status_code == 200
    r = await cliente.post("/usuarios/yo/identidades/github", json={}, headers=cab)
    assert r.status_code == 200


async def test_sin_contrasena_un_token_robado_no_cambia_como_se_entra(
    cliente, proveedores, perfil, monkeypatch, actores
):
    """Antes del arreglo, sin contraseña no se pedía NADA: con un access token robado se podía
    vincular el GitHub del atacante o activarle un MFA suyo y dejar fuera al dueño."""
    cab = await _cab_oauth(cliente)
    _mas_tarde(monkeypatch, 10)
    for ruta in (
        "/usuarios/yo/mfa/iniciar",
        "/usuarios/yo/identidades/github",
        "/usuarios/yo/identidades/google/desvincular",
    ):
        r = await cliente.post(ruta, json={}, headers=cab)
        assert r.status_code == 403, ruta
        assert "Vuelve a iniciar sesión" in r.json()["detail"]
    assert COOKIE_OAUTH not in _cookies(r)

    r = await cliente.get(
        "/auditoria?accion=mfa_reautenticacion_fallida", headers=actores.cab["admin"]
    )
    assert r.json()["total"] == 3


async def test_un_token_sin_hora_de_login_cuenta_como_antiguo(cliente, proveedores, perfil):
    cab = await _cab_oauth(cliente)
    yo = (await cliente.get("/usuarios/yo", headers=cab)).json()
    viejo = {"Authorization": f"Bearer {crear_token_acceso(yo['id'], 0)}"}
    r = await cliente.post("/usuarios/yo/mfa/iniciar", json={}, headers=viejo)
    assert r.status_code == 403


async def test_sin_contrasena_con_mfa_el_codigo_es_la_prueba(
    cliente, proveedores, perfil, monkeypatch
):
    monkeypatch.setattr(mfa, "_instante", lambda: 1_800_000_000.0)
    cab = await _cab_oauth(cliente)
    secreto = (await cliente.post("/usuarios/yo/mfa/iniciar", json={}, headers=cab)).json()[
        "secreto"
    ]
    r = await cliente.post(
        "/usuarios/yo/mfa/activar",
        json={"codigo": pyotp.TOTP(secreto).at(1_800_000_000)},
        headers=cab,
    )
    assert r.status_code == 200

    _mas_tarde(monkeypatch, 10)
    r = await cliente.post("/usuarios/yo/identidades/github", json={}, headers=cab)
    assert r.status_code == 403
    r = await cliente.post(
        "/usuarios/yo/identidades/github",
        json={"codigo": pyotp.TOTP(secreto).at(1_800_000_030)},
        headers=cab,
    )
    assert r.status_code == 200


async def test_desvincular_con_contrasena_la_exige(cliente, proveedores, perfil):
    await crear_usuario("yo@empresa.com")
    cab = await cabeceras(cliente, "yo@empresa.com")
    r = await cliente.post(
        "/usuarios/yo/identidades/github", json={"contrasena": CONTRASENA}, headers=cab
    )
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    await _vuelta(cliente, _cookies(r)[COOKIE_OAUTH], state, "github")

    r = await cliente.post(
        "/usuarios/yo/identidades/github/desvincular",
        json={"contrasena": "incorrecta-123"},
        headers=cab,
    )
    assert r.status_code == 422
    r = await cliente.post(
        "/usuarios/yo/identidades/github/desvincular",
        json={"contrasena": CONTRASENA},
        headers=cab,
    )
    assert r.status_code == 204
    assert (await cliente.get("/usuarios/yo", headers=cab)).json()["proveedores"] == []
