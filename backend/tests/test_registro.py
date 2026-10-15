"""Registro público y unión a una empresa con su código de invitación.

Una cuenta recién registrada es un usuario SIN empresa (pendiente): no ve nada hasta unirse.
Lo que se prueba aquí es sobre todo lo que un atacante intentaría: enumerar cuentas con el
registro, colarse como personal del MSSP, adivinar el código o reutilizar uno viejo.
"""

from app.limitador import limitador
from app.modelos import Rol
from tests.conftest import cabeceras, crear_incidente, crear_usuario, login

NUEVA = "contrasena-del-registro-1"


async def _registrar(cliente, email="nueva@test.com", contrasena=NUEVA):
    return await cliente.post("/auth/registro", json={"email": email, "contrasena": contrasena})


async def _cab(cliente, email="nueva@test.com", contrasena=NUEVA) -> dict:
    r = await cliente.post("/auth/login", json={"email": email, "contrasena": contrasena})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token_acceso']}"}


async def _unirse(cliente, cab, codigo):
    return await cliente.post("/usuarios/yo/empresa", json={"codigo": codigo}, headers=cab)


# --- Registro ---


async def test_registro_crea_una_cuenta_pendiente(cliente):
    r = await _registrar(cliente)
    assert r.status_code == 201
    yo = (await cliente.get("/usuarios/yo", headers=await _cab(cliente))).json()
    assert yo["rol"] == "usuario"
    assert yo["empresa_id"] is None
    assert yo["pendiente"] is True


async def test_registro_no_acepta_rol_ni_empresa(cliente, actores):
    # extra="forbid": nadie se registra como admin ni se mete solo en una empresa
    for extra in ({"rol": "admin"}, {"empresa_id": actores.empresa.id}):
        r = await cliente.post(
            "/auth/registro", json={"email": "x@test.com", "contrasena": NUEVA, **extra}
        )
        assert r.status_code == 422, extra


async def test_registro_exige_contrasena_de_12(cliente):
    assert (await _registrar(cliente, contrasena="corta")).status_code == 422


async def test_registro_con_email_existente_no_revela_nada_ni_cambia_nada(cliente, actores):
    nuevo = await _registrar(cliente, "otra@test.com")
    repetido = await _registrar(cliente, "USUARIO@test.com", contrasena="intento-de-pisarla-1")
    # Misma respuesta: el registro no sirve para averiguar qué emails tienen cuenta
    assert repetido.status_code == nuevo.status_code == 201
    assert repetido.json() == nuevo.json()
    # Y la cuenta existente sigue intacta: su contraseña vale, la del intento no
    await login(cliente, "usuario@test.com")
    r = await cliente.post(
        "/auth/login", json={"email": "usuario@test.com", "contrasena": "intento-de-pisarla-1"}
    )
    assert r.status_code == 401
    r = await cliente.get("/auditoria?accion=registro_duplicado", headers=actores.cab["admin"])
    assert r.json()["total"] == 1


async def test_registro_tiene_rate_limit(cliente):
    limitador.reset()
    codigos = [(await _registrar(cliente, f"r{i}@test.com")).status_code for i in range(6)]
    assert codigos[:5] == [201] * 5
    assert codigos[5] == 429


# --- Una cuenta pendiente no ve nada ---


async def test_pendiente_no_ve_ni_crea_incidencias(cliente, actores):
    await crear_incidente(cliente, actores.cab["usuario"])
    await _registrar(cliente)
    cab = await _cab(cliente)
    assert (await cliente.get("/incidentes", headers=cab)).status_code == 403
    r = await cliente.post(
        "/incidentes",
        json={"titulo": "x" * 5, "descripcion": "y", "severidad": "baja", "categoria": "otro"},
        headers=cab,
    )
    assert r.status_code == 403


async def test_pendiente_no_es_personal_del_mssp(cliente, actores):
    """La trampa clásica: «sin empresa» NO significa «personal de Kaelum». Si lo significara,
    cualquiera que se registre vería las incidencias de todos los clientes."""
    incidente = await crear_incidente(cliente, actores.cab["usuario"])
    await _registrar(cliente)
    cab = await _cab(cliente)
    r = await cliente.get(f"/incidentes/{incidente['id']}", headers=cab)
    assert r.status_code == 403
    for ruta in ("/usuarios", "/empresas", "/auditoria", "/eventos", "/mi-empresa"):
        assert (await cliente.get(ruta, headers=cab)).status_code == 403, ruta


async def test_pendiente_si_puede_ver_su_cuenta_y_cambiar_la_contrasena(cliente):
    await _registrar(cliente)
    cab = await _cab(cliente)
    assert (await cliente.get("/usuarios/yo", headers=cab)).status_code == 200
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": NUEVA, "contrasena_nueva": "otra-contrasena-larga-2"},
        headers=cab,
    )
    assert r.status_code == 204


# --- Unirse a una empresa ---


async def test_unirse_con_el_codigo_da_acceso_a_su_empresa(cliente, actores):
    await _registrar(cliente)
    cab = await _cab(cliente)
    r = await _unirse(cliente, cab, actores.empresa.codigo_invitacion)
    assert r.status_code == 200
    assert r.json()["empresa_id"] == actores.empresa.id
    assert r.json()["pendiente"] is False

    # Mismo token: la empresa se lee de la BD en cada petición
    incidente = await crear_incidente(cliente, cab)
    assert incidente["empresa_id"] == actores.empresa.id
    r = await cliente.get("/auditoria?accion=unirse_empresa", headers=actores.cab["admin"])
    assert r.json()["total"] == 1


async def test_el_codigo_se_admite_como_lo_teclee_la_gente(cliente, actores):
    await _registrar(cliente)
    tecleado = " " + actores.empresa.codigo_invitacion.lower().replace("-", " ") + " "
    r = await _unirse(cliente, await _cab(cliente), tecleado)
    assert r.status_code == 200


async def test_codigo_inventado_422_y_queda_auditado(cliente, actores):
    await _registrar(cliente)
    r = await _unirse(cliente, await _cab(cliente), "AAAA-BBBB-CCCC")
    assert r.status_code == 422
    r = await cliente.get("/auditoria?accion=union_empresa_fallida", headers=actores.cab["admin"])
    assert r.json()["total"] == 1


async def test_codigo_regenerado_el_viejo_ya_no_vale(cliente, actores):
    viejo = actores.empresa.codigo_invitacion
    r = await cliente.post(f"/empresas/{actores.empresa.id}/codigo", headers=actores.cab["admin"])
    nuevo = r.json()["codigo_invitacion"]
    assert nuevo != viejo

    await _registrar(cliente)
    cab = await _cab(cliente)
    assert (await _unirse(cliente, cab, viejo)).status_code == 422
    assert (await _unirse(cliente, cab, nuevo)).status_code == 200


async def test_no_se_une_a_una_empresa_dada_de_baja(cliente, actores):
    await cliente.patch(
        f"/empresas/{actores.empresa.id}", json={"activa": False}, headers=actores.cab["admin"]
    )
    await _registrar(cliente)
    r = await _unirse(cliente, await _cab(cliente), actores.empresa.codigo_invitacion)
    # Mismo mensaje que un código inventado: no confirma que la empresa exista
    assert r.status_code == 422


async def test_quien_ya_tiene_empresa_no_cambia_de_empresa_409(cliente, actores):
    codigo = actores.empresa.codigo_invitacion
    r = await _unirse(cliente, actores.cab["usuario"], codigo)
    assert r.status_code == 409
    # Tampoco el personal del MSSP: un admin con empresa sería un admin «de cliente»
    assert (await _unirse(cliente, actores.cab["admin"], codigo)).status_code == 409


async def test_un_gestor_nunca_se_une_por_codigo(cliente, actores):
    """Si pudiera, un código filtrado le haría responsable de una empresa ajena."""
    # Un gestor sin empresa no puede existir por la API: se crea a mano para probar la barrera
    await crear_usuario("gestor-suelto@test.com", rol=Rol.gestor)
    cab = await cabeceras(cliente, "gestor-suelto@test.com")
    r = await _unirse(cliente, cab, actores.empresa.codigo_invitacion)
    assert r.status_code == 409


async def test_unirse_tiene_rate_limit_contra_la_fuerza_bruta(cliente, actores):
    await _registrar(cliente)
    cab = await _cab(cliente)
    limitador.reset()
    codigos = [(await _unirse(cliente, cab, f"AAAA-BBBB-CCC{i}")).status_code for i in range(6)]
    assert codigos[:5] == [422] * 5
    assert codigos[5] == 429
    # Ni con el código bueno: el límite corta antes de mirar el código
    assert (await _unirse(cliente, cab, actores.empresa.codigo_invitacion)).status_code == 429
