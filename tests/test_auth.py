from datetime import timedelta

import jwt
from sqlalchemy.orm.attributes import set_committed_value

from app.config import obtener_configuracion
from app.db import FabricaSesion
from app.modelos import Rol, ahora
from app.repositorios import RepositorioTokens, RepositorioUsuarios
from tests.conftest import CONTRASENA, cabeceras, crear_usuario, login

REGISTRO = {"email": "nuevo@test.com", "contrasena": CONTRASENA}


async def test_registro_publico_eliminado(cliente):
    """Solo un admin da de alta cuentas: la ruta pública ya no existe."""
    r = await cliente.post("/auth/registro", json=REGISTRO)
    assert r.status_code == 404


async def test_login_correcto_devuelve_par_de_tokens(cliente):
    await crear_usuario("a@test.com")
    tokens = await login(cliente, "a@test.com")
    assert tokens["tipo_token"] == "bearer"
    assert tokens["token_acceso"] and tokens["token_refresco"]


async def test_login_mismo_error_si_el_email_no_existe(cliente):
    """Sin enumeración de usuarios: mismo código y mismo mensaje."""
    await crear_usuario("a@test.com")
    mala = await cliente.post("/auth/login", json={"email": "a@test.com", "contrasena": "x" * 12})
    no_existe = await cliente.post(
        "/auth/login", json={"email": "nadie@test.com", "contrasena": "x" * 12}
    )
    assert mala.status_code == no_existe.status_code == 401
    assert mala.json() == no_existe.json()


async def test_rate_limit_en_login(cliente):
    datos = {"email": "nadie@test.com", "contrasena": "x" * 12}
    codigos = [(await cliente.post("/auth/login", json=datos)).status_code for _ in range(6)]
    assert codigos[:5] == [401] * 5
    assert codigos[5] == 429


async def test_sin_token_401(cliente):
    r = await cliente.get("/usuarios/yo")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_token_manipulado_401(cliente):
    await crear_usuario("a@test.com")
    cab = await cabeceras(cliente, "a@test.com")
    token = cab["Authorization"].removeprefix("Bearer ")
    falso = jwt.encode(
        jwt.decode(token, options={"verify_signature": False}), "otro-secreto-" * 4, "HS256"
    )
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {falso}"})
    assert r.status_code == 401


async def test_token_caducado_401(cliente):
    usuario_id = await crear_usuario("a@test.com")
    config = obtener_configuracion()
    momento = ahora() - timedelta(hours=1)
    caducado = jwt.encode(
        {"sub": str(usuario_id), "tipo": "acceso", "ver": 0, "iat": momento, "exp": momento},
        config.jwt_secreto,
        config.jwt_algoritmo,
    )
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {caducado}"})
    assert r.status_code == 401


async def test_algoritmo_none_rechazado(cliente):
    usuario_id = await crear_usuario("a@test.com")
    sin_firma = jwt.encode({"sub": str(usuario_id), "tipo": "acceso"}, None, algorithm="none")
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {sin_firma}"})
    assert r.status_code == 401


async def test_refresco_rota_el_token(cliente):
    await crear_usuario("a@test.com")
    viejo = (await login(cliente, "a@test.com"))["token_refresco"]

    r = await cliente.post("/auth/refrescar", json={"token_refresco": viejo})
    assert r.status_code == 200
    nuevo = r.json()["token_refresco"]
    assert nuevo != viejo

    r = await cliente.get(
        "/usuarios/yo", headers={"Authorization": f"Bearer {r.json()['token_acceso']}"}
    )
    assert r.status_code == 200


async def test_reutilizar_token_revocado_revoca_toda_la_familia(cliente):
    await crear_usuario("a@test.com")
    robado = (await login(cliente, "a@test.com"))["token_refresco"]
    legitimo = (await cliente.post("/auth/refrescar", json={"token_refresco": robado})).json()[
        "token_refresco"
    ]

    # El atacante reutiliza el token ya rotado
    r = await cliente.post("/auth/refrescar", json={"token_refresco": robado})
    assert r.status_code == 401
    # Y el token legítimo también queda invalidado
    r = await cliente.post("/auth/refrescar", json={"token_refresco": legitimo})
    assert r.status_code == 401


async def test_reutilizacion_tumba_tambien_el_access_del_atacante(cliente):
    await crear_usuario("a@test.com")
    otro_dispositivo = await login(cliente, "a@test.com")
    copia = (await login(cliente, "a@test.com"))["token_refresco"]

    # El atacante usa su copia primero y consigue un access token válido
    atacante = (await cliente.post("/auth/refrescar", json={"token_refresco": copia})).json()
    cab_atacante = {"Authorization": f"Bearer {atacante['token_acceso']}"}
    assert (await cliente.get("/usuarios/yo", headers=cab_atacante)).status_code == 200

    # El legítimo presenta la misma copia (ya rotada): reutilización detectada
    r = await cliente.post("/auth/refrescar", json={"token_refresco": copia})
    assert r.status_code == 401
    # El access del atacante cae YA, sin esperar a que caduque
    assert (await cliente.get("/usuarios/yo", headers=cab_atacante)).status_code == 401

    # Otro dispositivo (otra familia) conserva su refresh y se recupera sin volver a entrar
    r = await cliente.post(
        "/auth/refrescar", json={"token_refresco": otro_dispositivo["token_refresco"]}
    )
    assert r.status_code == 200
    cab = {"Authorization": f"Bearer {r.json()['token_acceso']}"}
    assert (await cliente.get("/usuarios/yo", headers=cab)).status_code == 200


async def test_dos_refrescos_simultaneos_con_el_mismo_token_solo_gana_uno(cliente, monkeypatch):
    """Carrera TOCTOU: las dos peticiones leen el token antes de que ninguna lo marque como
    usado. Se simula devolviendo a la segunda una lectura vieja (sin revocar)."""
    await crear_usuario("a@test.com")
    token = (await login(cliente, "a@test.com"))["token_refresco"]

    vistos = set()
    original = RepositorioTokens.por_hash

    async def por_hash(self, hash_token):
        fila = await original(self, hash_token)
        if fila is not None and fila.id in vistos:
            # Lo que vería si hubiera leído a la vez que la primera. Sin marcarlo como cambio:
            # si no, el autoflush escribiría ese NULL en la BD y deshacería la revocación
            set_committed_value(fila, "revocado_en", None)
        elif fila is not None:
            vistos.add(fila.id)
        return fila

    monkeypatch.setattr(RepositorioTokens, "por_hash", por_hash)
    primera = await cliente.post("/auth/refrescar", json={"token_refresco": token})
    assert primera.status_code == 200
    segunda = await cliente.post("/auth/refrescar", json={"token_refresco": token})
    # Pasa la lectura, pero el UPDATE condicional ve que ya estaba usado: reutilización
    assert segunda.status_code == 401
    monkeypatch.undo()

    # Y se trata como un robo: la familia entera queda revocada
    r = await cliente.post(
        "/auth/refrescar", json={"token_refresco": primera.json()["token_refresco"]}
    )
    assert r.status_code == 401


async def test_logout_revoca_el_refresco(cliente):
    await crear_usuario("a@test.com")
    refresco = (await login(cliente, "a@test.com"))["token_refresco"]
    r = await cliente.post("/auth/logout", json={"token_refresco": refresco})
    assert r.status_code == 204
    r = await cliente.post("/auth/refrescar", json={"token_refresco": refresco})
    assert r.status_code == 401


async def test_refresco_inventado_401(cliente):
    r = await cliente.post("/auth/refrescar", json={"token_refresco": "inventado"})
    assert r.status_code == 401


async def test_token_sin_version_de_sesion_401(cliente):
    # Firma buena y sin caducar, pero sin "ver": no hay forma de saber si se revocó
    usuario_id = await crear_usuario("a@test.com")
    config = obtener_configuracion()
    momento = ahora()
    caduca = momento + timedelta(minutes=5)
    sin_version = jwt.encode(
        {"sub": str(usuario_id), "tipo": "acceso", "iat": momento, "exp": caduca},
        config.jwt_secreto,
        config.jwt_algoritmo,
    )
    r = await cliente.get("/usuarios/yo", headers={"Authorization": f"Bearer {sin_version}"})
    assert r.status_code == 401


async def test_el_rol_sale_de_la_bd_no_del_token(cliente):
    usuario_id = await crear_usuario("a@test.com")
    cab = await cabeceras(cliente, "a@test.com")
    assert (await cliente.get("/usuarios", headers=cab)).status_code == 403

    # Mismo token, rol cambiado directamente en la BD: el permiso cambia en la siguiente petición
    async with FabricaSesion() as sesion:
        usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
        usuario.rol = Rol.admin
        await sesion.commit()
    assert (await cliente.get("/usuarios", headers=cab)).status_code == 200
