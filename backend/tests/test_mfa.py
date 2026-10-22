"""Verificación en dos pasos (TOTP): alta, login en dos pasos, anti-replay, bloqueo, códigos de
recuperación y obligación para el personal del MSSP."""

import pyotp
import pytest

from app.config import obtener_configuracion
from app.db import FabricaSesion
from app.limitador import limitador
from app.modelos import Rol
from app.repositorios import RepositorioUsuarios
from app.seguridad import descifrar_secreto
from app.servicios import mfa
from tests.conftest import CONTRASENA, cabeceras, crear_usuario

EMAIL = "mfa@test.com"
T0 = 1_800_000_000  # instante fijo: múltiplo de 30, así cada +30 s es un paso TOTP nuevo


@pytest.fixture
def reloj(monkeypatch):
    """Fija el reloj del TOTP. `reloj.avanzar()` salta al siguiente paso de 30 s."""

    class Reloj:
        ahora = float(T0)

        def avanzar(self, segundos: int = 30) -> None:
            self.ahora += segundos

        def codigo(self, secreto: str) -> str:
            return pyotp.TOTP(secreto).at(self.ahora)

    r = Reloj()
    monkeypatch.setattr(mfa, "_instante", lambda: r.ahora)
    return r


async def _activar(cliente, cab: dict, reloj) -> tuple[str, list[str]]:
    r = await cliente.post("/usuarios/yo/mfa/iniciar", json={"contrasena": CONTRASENA}, headers=cab)
    assert r.status_code == 200, r.text
    secreto = r.json()["secreto"]
    r = await cliente.post(
        "/usuarios/yo/mfa/activar", json={"codigo": reloj.codigo(secreto)}, headers=cab
    )
    assert r.status_code == 200, r.text
    limitador.reset()
    return secreto, r.json()["codigos"]


async def _desafio(cliente, email: str = EMAIL) -> str:
    r = await cliente.post("/auth/login", json={"email": email, "contrasena": CONTRASENA})
    assert r.status_code == 200, r.text
    assert r.json()["mfa_requerido"] is True
    assert "token_acceso" not in r.json()
    return r.json()["desafio"]


@pytest.fixture
async def con_mfa(cliente, reloj):
    """Usuario con MFA activo: (secreto, códigos de recuperación)."""
    await crear_usuario(EMAIL)
    cab = await cabeceras(cliente, EMAIL)
    secreto, codigos = await _activar(cliente, cab, reloj)
    reloj.avanzar()  # el código de la activación ya está gastado
    return secreto, codigos


async def test_alta_devuelve_qr_y_no_activa_hasta_confirmar(cliente):
    await crear_usuario(EMAIL)
    cab = await cabeceras(cliente, EMAIL)
    r = await cliente.post("/usuarios/yo/mfa/iniciar", json={"contrasena": CONTRASENA}, headers=cab)
    assert r.status_code == 200
    alta = r.json()
    assert alta["uri"].startswith("otpauth://totp/")
    assert "issuer=Kaelum%20Umbral" in alta["uri"]
    assert len(alta["qr"]) == len(alta["qr"][0]) >= 21  # matriz cuadrada
    assert set("".join(alta["qr"])) <= {"0", "1"}

    # Sin confirmar con un código, el login sigue siendo de un paso
    r = await cliente.post("/auth/login", json={"email": EMAIL, "contrasena": CONTRASENA})
    assert "token_acceso" in r.json()


async def test_alta_exige_la_contrasena(cliente):
    await crear_usuario(EMAIL)
    cab = await cabeceras(cliente, EMAIL)
    for cuerpo in ({}, {"contrasena": "incorrecta-123"}):
        r = await cliente.post("/usuarios/yo/mfa/iniciar", json=cuerpo, headers=cab)
        assert r.status_code == 422


async def test_activar_con_codigo_incorrecto_422(cliente, reloj):
    await crear_usuario(EMAIL)
    cab = await cabeceras(cliente, EMAIL)
    await cliente.post("/usuarios/yo/mfa/iniciar", json={"contrasena": CONTRASENA}, headers=cab)
    r = await cliente.post("/usuarios/yo/mfa/activar", json={"codigo": "000000"}, headers=cab)
    assert r.status_code == 422


async def test_login_en_dos_pasos(cliente, con_mfa, reloj):
    secreto, codigos = con_mfa
    assert len(codigos) == 10
    desafio = await _desafio(cliente)

    r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": reloj.codigo(secreto)})
    assert r.status_code == 200, r.text
    cab = {"Authorization": f"Bearer {r.json()['token_acceso']}"}
    yo = (await cliente.get("/usuarios/yo", headers=cab)).json()
    assert yo["mfa_activo"] is True


async def test_tolera_un_paso_de_desfase_y_no_mas(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    desafio = await _desafio(cliente)
    reloj.avanzar(60)
    viejo = pyotp.TOTP(secreto).at(reloj.ahora - 60)
    r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": viejo})
    assert r.status_code == 401
    anterior = pyotp.TOTP(secreto).at(reloj.ahora - 30)
    r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": anterior})
    assert r.status_code == 200


async def test_un_codigo_no_vale_dos_veces(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    codigo = reloj.codigo(secreto)
    r = await cliente.post("/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": codigo})
    assert r.status_code == 200
    # Mismo código, mismo paso: quien lo haya visto por encima del hombro llega tarde
    r = await cliente.post("/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": codigo})
    assert r.status_code == 401


async def test_codigo_de_recuperacion_de_un_solo_uso(cliente, con_mfa):
    _, codigos = con_mfa
    # Como lo teclearía alguien: minúsculas y sin guiones
    tecleado = codigos[0].replace("-", "").lower()
    r = await cliente.post(
        "/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": tecleado}
    )
    assert r.status_code == 200
    r = await cliente.post(
        "/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": codigos[0]}
    )
    assert r.status_code == 401


async def test_cinco_fallos_bloquean_aunque_el_codigo_sea_bueno(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    desafio = await _desafio(cliente)
    for _ in range(5):
        r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": "123456"})
        assert r.status_code == 401
    limitador.reset()  # el bloqueo es por cuenta, no por IP: se descarta el límite por IP
    r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": reloj.codigo(secreto)})
    assert r.status_code == 401
    assert "Espera" in r.json()["detail"]


async def test_el_desafio_no_sirve_como_bearer(cliente, con_mfa):
    desafio = await _desafio(cliente)
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {desafio}"})
    assert r.status_code == 401


async def test_un_access_token_no_sirve_como_desafio(cliente, reloj):
    await crear_usuario(EMAIL)
    token = (await cabeceras(cliente, EMAIL))["Authorization"].split()[1]
    r = await cliente.post("/auth/mfa", json={"desafio": token, "codigo": "123456"})
    assert r.status_code == 401


async def test_el_desafio_muere_si_se_cierran_las_sesiones(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    desafio = await _desafio(cliente)
    async with FabricaSesion() as sesion:
        usuario = await RepositorioUsuarios(sesion).por_email(EMAIL)
        usuario.version_sesion += 1
        await sesion.commit()
    r = await cliente.post("/auth/mfa", json={"desafio": desafio, "codigo": reloj.codigo(secreto)})
    assert r.status_code == 401


async def test_login_web_con_mfa_no_pone_cookie_hasta_el_segundo_paso(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    r = await cliente.post("/auth/web/login", json={"email": EMAIL, "contrasena": CONTRASENA})
    assert r.json()["mfa_requerido"] is True
    assert "set-cookie" not in r.headers
    r = await cliente.post(
        "/auth/web/mfa", json={"desafio": r.json()["desafio"], "codigo": reloj.codigo(secreto)}
    )
    assert r.status_code == 200
    assert "token_refresco" not in r.json()
    assert "httponly" in r.headers["set-cookie"].lower()


async def test_el_secreto_va_cifrado_y_ligado_a_su_usuario(cliente, con_mfa):
    secreto, _ = con_mfa
    async with FabricaSesion() as sesion:
        usuario = await RepositorioUsuarios(sesion).por_email(EMAIL)
        assert secreto not in usuario.mfa_secreto
        assert descifrar_secreto(usuario.mfa_secreto, usuario.id) == secreto
        # Copiado a la fila de otra cuenta, no se descifra
        assert descifrar_secreto(usuario.mfa_secreto, usuario.id + 1) is None


async def _sesion_mfa(cliente, reloj, secreto: str) -> dict:
    r = await cliente.post(
        "/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": reloj.codigo(secreto)}
    )
    reloj.avanzar()
    return {"Authorization": f"Bearer {r.json()['token_acceso']}"}


async def test_regenerar_codigos_invalida_los_anteriores(cliente, con_mfa, reloj):
    secreto, viejos = con_mfa
    cab = await _sesion_mfa(cliente, reloj, secreto)
    r = await cliente.post(
        "/usuarios/yo/mfa/codigos", json={"codigo": reloj.codigo(secreto)}, headers=cab
    )
    assert r.status_code == 200
    nuevos = r.json()["codigos"]
    assert not set(nuevos) & set(viejos)
    r = await cliente.post(
        "/auth/mfa", json={"desafio": await _desafio(cliente), "codigo": viejos[1]}
    )
    assert r.status_code == 401


async def test_desactivar_exige_contrasena_y_codigo(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    cab = await _sesion_mfa(cliente, reloj, secreto)
    r = await cliente.post(
        "/usuarios/yo/mfa/desactivar",
        json={"contrasena": "incorrecta-123", "codigo": reloj.codigo(secreto)},
        headers=cab,
    )
    assert r.status_code == 422
    r = await cliente.post(
        "/usuarios/yo/mfa/desactivar",
        json={"contrasena": CONTRASENA, "codigo": reloj.codigo(secreto)},
        headers=cab,
    )
    assert r.status_code == 204
    r = await cliente.post("/auth/login", json={"email": EMAIL, "contrasena": CONTRASENA})
    assert "token_acceso" in r.json()


async def test_admin_restablece_el_mfa_y_cierra_sus_sesiones(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    cab_usuario = await _sesion_mfa(cliente, reloj, secreto)
    await crear_usuario("jefa@test.com", Rol.admin)
    cab_admin = await cabeceras(cliente, "jefa@test.com")
    usuario_id = (await cliente.get("/usuarios/yo", headers=cab_usuario)).json()["id"]

    r = await cliente.delete(f"/usuarios/{usuario_id}/mfa", headers=cab_admin)
    assert r.status_code == 200
    assert r.json()["mfa_activo"] is False
    assert (await cliente.get("/usuarios/yo", headers=cab_usuario)).status_code == 401

    r = await cliente.get("/auditoria?accion=restablecer_mfa", headers=cab_admin)
    assert r.json()["total"] == 1


async def test_solo_un_admin_restablece_el_mfa(cliente, con_mfa, reloj):
    secreto, _ = con_mfa
    cab = await _sesion_mfa(cliente, reloj, secreto)
    usuario_id = (await cliente.get("/usuarios/yo", headers=cab)).json()["id"]
    assert (await cliente.delete(f"/usuarios/{usuario_id}/mfa", headers=cab)).status_code == 403


async def test_el_personal_sin_mfa_solo_ve_su_cuenta(cliente, reloj, monkeypatch):
    monkeypatch.setattr(obtener_configuracion(), "mfa_obligatorio_personal", True)
    await crear_usuario("jefa@test.com", Rol.admin)
    cab = await cabeceras(cliente, "jefa@test.com")

    assert (await cliente.get("/usuarios", headers=cab)).status_code == 403
    # Tampoco el stream, que no usa la dependencia `Admin` sino la suya propia
    assert (await cliente.get("/eventos/stream", headers=cab)).status_code == 403
    yo = (await cliente.get("/usuarios/yo", headers=cab)).json()
    assert yo["mfa_por_activar"] is True and yo["mfa_obligatorio"] is True

    secreto, _ = await _activar(cliente, cab, reloj)
    assert (await cliente.get("/usuarios", headers=cab)).status_code == 200

    # Y no se lo puede quitar: su rol lo exige
    reloj.avanzar()
    r = await cliente.post(
        "/usuarios/yo/mfa/desactivar",
        json={"contrasena": CONTRASENA, "codigo": reloj.codigo(secreto)},
        headers=cab,
    )
    assert r.status_code == 409


async def test_el_cliente_no_esta_obligado(cliente, monkeypatch, actores):
    monkeypatch.setattr(obtener_configuracion(), "mfa_obligatorio_personal", True)
    r = await cliente.get("/incidentes", headers=actores.cab["usuario"])
    assert r.status_code == 200
