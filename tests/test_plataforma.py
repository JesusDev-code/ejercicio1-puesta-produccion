async def test_salud(cliente):
    r = await cliente.get("/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "bd": "ok"}


async def test_cabeceras_de_seguridad(cliente):
    r = await cliente.get("/salud")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "max-age" in r.headers["strict-transport-security"]
    assert r.headers["content-security-policy"].startswith("default-src 'none'")


async def test_cors_permite_origen_de_la_lista_blanca(cliente):
    r = await cliente.options(
        "/incidentes",
        headers={"Origin": "https://app.ejemplo.com", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers["access-control-allow-origin"] == "https://app.ejemplo.com"


async def test_cors_rechaza_origen_desconocido(cliente):
    r = await cliente.options(
        "/incidentes",
        headers={"Origin": "https://malicioso.com", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in r.headers


async def test_error_de_validacion_422(cliente):
    r = await cliente.post("/auth/login", json={"email": "no-es-email", "contrasena": "x"})
    assert r.status_code == 422


async def test_quitar_prefijo_api():
    """Detrás de Traefik la API recibe /api/...; sin strip path, la propia API lo quita."""
    from httpx import ASGITransport, AsyncClient

    from app.main import QuitarPrefijo, app

    envuelta = QuitarPrefijo(app, "/api")
    async with AsyncClient(transport=ASGITransport(app=envuelta), base_url="http://test") as c:
        assert (await c.get("/api/salud")).status_code == 200
        assert (await c.get("/salud")).status_code == 200
        assert (await c.get("/apix/salud")).status_code == 404
