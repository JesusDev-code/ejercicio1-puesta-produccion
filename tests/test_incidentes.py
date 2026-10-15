from tests.conftest import crear_incidente


async def asignar(cliente, actores, incidente_id, analista="analista"):
    r = await cliente.patch(
        f"/incidentes/{incidente_id}/asignar",
        json={"analista_id": actores.ids[analista]},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 200, r.text
    return r.json()


async def estado(cliente, cab, incidente_id, nuevo):
    return await cliente.patch(
        f"/incidentes/{incidente_id}/estado", json={"estado": nuevo}, headers=cab
    )


# --- Visibilidad e IDOR ---


async def test_crear_incidente_queda_abierto_y_es_del_reportante(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    assert inc["estado"] == "abierto"
    assert inc["reportante_id"] == actores.ids["usuario"]
    assert "notas_internas" not in inc


async def test_crear_rechaza_campos_protegidos(cliente, actores):
    r = await cliente.post(
        "/incidentes",
        json={
            "titulo": "x" * 5,
            "descripcion": "d",
            "severidad": "baja",
            "categoria": "otro",
            "estado": "cerrado",
        },
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 422


async def test_usuario_no_ve_incidente_ajeno_404(cliente, actores):
    """IDOR: 404 y no 403, para no confirmar que el recurso existe."""
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.get(f"/incidentes/{inc['id']}", headers=actores.cab["otro"])
    assert r.status_code == 404


async def test_listado_del_usuario_solo_trae_los_suyos(cliente, actores):
    await crear_incidente(cliente, actores.cab["usuario"])
    await crear_incidente(cliente, actores.cab["otro"])
    r = await cliente.get("/incidentes", headers=actores.cab["usuario"])
    cuerpo = r.json()
    assert cuerpo["total"] == 1
    assert all(i["reportante_id"] == actores.ids["usuario"] for i in cuerpo["elementos"])


async def test_analista_solo_ve_los_asignados(cliente, actores):
    asignado = await crear_incidente(cliente, actores.cab["usuario"])
    no_asignado = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, asignado["id"])

    r = await cliente.get("/incidentes", headers=actores.cab["analista"])
    assert [i["id"] for i in r.json()["elementos"]] == [asignado["id"]]

    r = await cliente.get(f"/incidentes/{no_asignado['id']}", headers=actores.cab["analista"])
    assert r.status_code == 404


async def test_admin_ve_todos(cliente, actores):
    await crear_incidente(cliente, actores.cab["usuario"])
    await crear_incidente(cliente, actores.cab["otro"])
    r = await cliente.get("/incidentes", headers=actores.cab["admin"])
    assert r.json()["total"] == 2


async def test_paginacion_y_limite_maximo(cliente, actores):
    for _ in range(3):
        await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.get("/incidentes?limite=2", headers=actores.cab["usuario"])
    assert r.json()["total"] == 3 and len(r.json()["elementos"]) == 2
    r = await cliente.get("/incidentes?limite=101", headers=actores.cab["usuario"])
    assert r.status_code == 422


async def test_filtro_por_severidad(cliente, actores):
    await crear_incidente(cliente, actores.cab["usuario"], severidad="critica")
    await crear_incidente(cliente, actores.cab["usuario"], severidad="baja")
    r = await cliente.get("/incidentes?severidad=critica", headers=actores.cab["usuario"])
    assert [i["severidad"] for i in r.json()["elementos"]] == ["critica"]


# --- Notas internas ---


async def test_notas_internas_no_llegan_al_reportante(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}/notas",
        json={"notas_internas": "IP origen 10.0.0.5"},
        headers=actores.cab["analista"],
    )
    assert r.status_code == 200
    assert r.json()["notas_internas"] == "IP origen 10.0.0.5"

    vista_reportante = await cliente.get(f"/incidentes/{inc['id']}", headers=actores.cab["usuario"])
    assert "notas_internas" not in vista_reportante.json()

    listado = await cliente.get("/incidentes", headers=actores.cab["usuario"])
    assert "notas_internas" not in listado.json()["elementos"][0]


async def test_reportante_no_puede_escribir_notas_403(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}/notas",
        json={"notas_internas": "x"},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 403


# --- Edición ---


async def test_reportante_edita_mientras_esta_abierto(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}", json={"titulo": "Nuevo título"}, headers=actores.cab["usuario"]
    )
    assert r.status_code == 200 and r.json()["titulo"] == "Nuevo título"


async def test_reportante_no_edita_fuera_de_abierto_409(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])
    await estado(cliente, actores.cab["analista"], inc["id"], "en_analisis")
    r = await cliente.patch(
        f"/incidentes/{inc['id']}", json={"titulo": "Cambio tardío"}, headers=actores.cab["usuario"]
    )
    assert r.status_code == 409


async def test_editar_no_permite_cambiar_severidad(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}", json={"severidad": "critica"}, headers=actores.cab["usuario"]
    )
    assert r.status_code == 422


# --- Ciclo de vida ---


async def test_ciclo_completo(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])
    for nuevo in ("en_analisis", "resuelto", "cerrado"):
        r = await estado(cliente, actores.cab["analista"], inc["id"], nuevo)
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == nuevo


async def test_transicion_invalida_409(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])
    r = await estado(cliente, actores.cab["analista"], inc["id"], "cerrado")
    assert r.status_code == 409


async def test_en_analisis_sin_analista_409(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await estado(cliente, actores.cab["admin"], inc["id"], "en_analisis")
    assert r.status_code == 409


async def test_reportante_no_cambia_estado_403(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await estado(cliente, actores.cab["usuario"], inc["id"], "en_analisis")
    assert r.status_code == 403


async def test_solo_admin_reabre(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])
    for nuevo in ("en_analisis", "resuelto", "cerrado"):
        await estado(cliente, actores.cab["analista"], inc["id"], nuevo)

    r = await estado(cliente, actores.cab["analista"], inc["id"], "abierto")
    assert r.status_code == 403
    r = await estado(cliente, actores.cab["admin"], inc["id"], "abierto")
    assert r.status_code == 200 and r.json()["estado"] == "abierto"


# --- Asignación ---


async def test_solo_admin_asigna_403(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}/asignar",
        json={"analista_id": actores.ids["analista"]},
        headers=actores.cab["analista"],
    )
    assert r.status_code == 403


async def test_no_se_asigna_a_quien_no_es_analista_422(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.patch(
        f"/incidentes/{inc['id']}/asignar",
        json={"analista_id": actores.ids["otro"]},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 422


async def test_reasignar_quita_el_acceso_al_analista_anterior(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"], "analista")
    await asignar(cliente, actores, inc["id"], "analista2")
    r = await cliente.get(f"/incidentes/{inc['id']}", headers=actores.cab["analista"])
    assert r.status_code == 404


# --- Borrado lógico ---


async def test_borrado_logico_solo_admin(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    r = await cliente.delete(f"/incidentes/{inc['id']}", headers=actores.cab["usuario"])
    assert r.status_code == 403

    r = await cliente.delete(f"/incidentes/{inc['id']}", headers=actores.cab["admin"])
    assert r.status_code == 204

    r = await cliente.get(f"/incidentes/{inc['id']}", headers=actores.cab["admin"])
    assert r.status_code == 404
    r = await cliente.get("/incidentes", headers=actores.cab["admin"])
    assert r.json()["total"] == 0


# --- Roles y auditoría ---


async def test_cambio_de_rol_es_inmediato(cliente, actores):
    """El rol se lee de la BD en cada petición: el token antiguo ya no da privilegios."""
    r = await cliente.patch(
        f"/usuarios/{actores.ids['analista']}/rol",
        json={"rol": "usuario"},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 200
    r = await cliente.get("/usuarios/yo", headers=actores.cab["analista"])
    assert r.json()["rol"] == "usuario"


async def test_admin_no_cambia_su_propio_rol(cliente, actores):
    r = await cliente.patch(
        f"/usuarios/{actores.ids['admin']}/rol",
        json={"rol": "usuario"},
        headers=actores.cab["admin"],
    )
    assert r.status_code == 409


async def test_usuario_no_cambia_roles_403(cliente, actores):
    r = await cliente.patch(
        f"/usuarios/{actores.ids['usuario']}/rol",
        json={"rol": "admin"},
        headers=actores.cab["usuario"],
    )
    assert r.status_code == 403


async def test_auditoria_registra_acciones_y_es_solo_admin(cliente, actores):
    inc = await crear_incidente(cliente, actores.cab["usuario"])
    await asignar(cliente, actores, inc["id"])

    r = await cliente.get("/auditoria", headers=actores.cab["usuario"])
    assert r.status_code == 403

    r = await cliente.get("/auditoria", headers=actores.cab["admin"])
    acciones = {e["accion"] for e in r.json()["elementos"]}
    assert {"login", "crear_incidente", "asignar_incidente"} <= acciones
