from tests.conftest import CONTRASENA, crear_incidente, login

NUEVA = "otra-contrasena-segura-456"


# --- Filtros del listado de usuarios ---


async def test_filtrar_usuarios_por_rol(cliente, actores):
    r = await cliente.get("/usuarios", params={"rol": "analista"}, headers=actores.cab["admin"])
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["total"] == 2
    assert {u["rol"] for u in cuerpo["elementos"]} == {"analista"}


async def test_filtrar_usuarios_por_email_parcial_sin_distinguir_mayusculas(cliente, actores):
    r = await cliente.get("/usuarios", params={"email": "ANALISTA"}, headers=actores.cab["admin"])
    emails = {u["email"] for u in r.json()["elementos"]}
    assert emails == {"analista@test.com", "analista2@test.com"}


async def test_filtro_email_trata_comodines_como_literales(cliente, actores):
    """Un `%` del cliente no debe convertirse en "cualquier cosa" dentro del LIKE."""
    r = await cliente.get("/usuarios", params={"email": "%"}, headers=actores.cab["admin"])
    assert r.json()["total"] == 0


async def test_filtro_rol_invalido_422(cliente, actores):
    r = await cliente.get("/usuarios", params={"rol": "root"}, headers=actores.cab["admin"])
    assert r.status_code == 422


# --- Emails en incidentes y auditoría ---


async def test_incidente_incluye_emails_de_reportante_y_analista(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    assert inc["reportante_email"] == "usuario@test.com"
    assert inc["analista_email"] is None

    r = await cliente.patch(
        f"/incidentes/{inc['id']}/asignar",
        json={"analista_id": actores.ids["analista"]},
        headers=actores.cab["admin"],
    )
    assert r.json()["analista_email"] == "analista@test.com"

    r = await cliente.get(f"/incidentes/{inc['id']}", headers=actores.cab["usuario"])
    assert r.json()["analista_email"] == "analista@test.com"
    assert "notas_internas" not in r.json()


async def test_listado_incluye_emails(cliente, actores):
    await crear_incidente(cliente, actores.cab["usuario"])
    await crear_incidente(cliente, actores.cab["otro"])
    r = await cliente.get("/incidentes", headers=actores.cab["admin"])
    emails = {i["reportante_email"] for i in r.json()["elementos"]}
    assert emails == {"usuario@test.com", "otro@test.com"}


async def test_auditoria_incluye_email_del_usuario(cliente, actores):
    r = await cliente.get("/auditoria", params={"accion": "login"}, headers=actores.cab["admin"])
    registros = r.json()["elementos"]
    assert registros
    assert all(reg["usuario_email"] for reg in registros)
    assert "admin@test.com" in {reg["usuario_email"] for reg in registros}


# --- Cambio de contraseña ---


async def test_cambiar_contrasena_revoca_sesiones_y_cambia_credenciales(cliente, actores):
    tokens = await login(cliente, "usuario@test.com")
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": CONTRASENA, "contrasena_nueva": NUEVA},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 204

    # Los refresh previos quedan revocados
    r = await cliente.post("/auth/refrescar", json={"token_refresco": tokens["token_refresco"]})
    assert r.status_code == 401

    viejo = await cliente.post(
        "/auth/login", json={"email": "usuario@test.com", "contrasena": CONTRASENA}
    )
    assert viejo.status_code == 401
    nuevo = await cliente.post(
        "/auth/login", json={"email": "usuario@test.com", "contrasena": NUEVA}
    )
    assert nuevo.status_code == 200


async def test_cambiar_contrasena_con_actual_incorrecta_422_y_se_audita(cliente, actores):
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": "no-es-esta-contrasena", "contrasena_nueva": NUEVA},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 422

    r = await cliente.get(
        "/auditoria", params={"accion": "cambio_contrasena_fallido"}, headers=actores.cab["admin"]
    )
    assert r.json()["total"] == 1


async def test_cambiar_contrasena_nueva_corta_422(cliente, actores):
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": CONTRASENA, "contrasena_nueva": "corta"},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 422


async def test_cambiar_contrasena_igual_a_la_actual_422(cliente, actores):
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": CONTRASENA, "contrasena_nueva": CONTRASENA},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 422


async def test_cambiar_contrasena_sin_token_401(cliente):
    r = await cliente.patch(
        "/usuarios/yo/contrasena",
        json={"contrasena_actual": CONTRASENA, "contrasena_nueva": NUEVA},
    )
    assert r.status_code == 401


async def test_cambiar_contrasena_tiene_rate_limit(cliente, actores):
    codigos = []
    for _ in range(6):
        r = await cliente.patch(
            "/usuarios/yo/contrasena",
            json={"contrasena_actual": "incorrecta-1234", "contrasena_nueva": NUEVA},
            headers=actores.cab["usuario"],
        )
        codigos.append(r.status_code)
    assert codigos[-1] == 429


# --- Activar y desactivar usuarios ---


async def activo(cliente, actores, clave, valor, como="admin"):
    return await cliente.patch(
        f"/usuarios/{actores.ids[clave]}/activo",
        json={"activo": valor},
        headers=actores.cab[como],
    )


async def test_desactivar_usuario_corta_el_acceso_al_momento(cliente, actores):
    r = await activo(cliente, actores, "otro", False)
    assert r.status_code == 200
    assert r.json()["activo"] is False

    # El access token emitido antes deja de valer en la siguiente petición
    r = await cliente.get("/usuarios/yo", headers=actores.cab["otro"])
    assert r.status_code == 401
    r = await cliente.post("/auth/login", json={"email": "otro@test.com", "contrasena": CONTRASENA})
    assert r.status_code == 401


async def test_reactivar_usuario_le_devuelve_el_acceso(cliente, actores):
    await activo(cliente, actores, "otro", False)
    r = await activo(cliente, actores, "otro", True)
    assert r.json()["activo"] is True
    await login(cliente, "otro@test.com")

    r = await cliente.get(
        "/auditoria", params={"accion": "reactivar_usuario"}, headers=actores.cab["admin"]
    )
    assert r.json()["total"] == 1


async def test_admin_no_puede_desactivarse_a_si_mismo_409(cliente, actores):
    r = await activo(cliente, actores, "admin", False)
    assert r.status_code == 409


async def test_desactivar_requiere_admin_403(cliente, actores):
    r = await activo(cliente, actores, "otro", False, como="analista")
    assert r.status_code == 403


async def test_desactivar_usuario_inexistente_404(cliente, actores):
    r = await cliente.patch(
        "/usuarios/99999/activo", json={"activo": False}, headers=actores.cab["admin"]
    )
    assert r.status_code == 404
