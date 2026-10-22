import os

# La configuración se lee al importar la app: el entorno se fija antes de cualquier import
os.environ["ENTORNO"] = "test"
os.environ["JWT_SECRETO"] = "secreto-de-test-con-mas-de-32-caracteres"
os.environ["MFA_CLAVE"] = "clave-mfa-de-test-con-mas-de-32-caracteres"
# La obligación de MFA del personal se prueba en test_mfa.py; el resto de tests no la necesita
os.environ["MFA_OBLIGATORIO_PERSONAL"] = "false"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")
os.environ["CORS_ORIGENES"] = "https://app.ejemplo.com"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import Base, FabricaSesion, motor  # noqa: E402
from app.limitador import limitador  # noqa: E402
from app.main import app  # noqa: E402
from app.modelos import Empresa, Rol  # noqa: E402
from app.repositorios import RepositorioUsuarios  # noqa: E402
from app.seguridad import hashear_contrasena  # noqa: E402

CONTRASENA = "contrasena-segura-123"


@pytest.fixture(autouse=True)
async def bd():
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    limitador.reset()
    yield
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
    # Cada test corre en su propio event loop: no se reutilizan conexiones entre loops
    await motor.dispose()


@pytest.fixture
async def cliente():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def crear_usuario(email: str, rol: Rol = Rol.usuario, empresa_id: int | None = None) -> int:
    async with FabricaSesion() as sesion:
        usuario = await RepositorioUsuarios(sesion).crear(
            email, hashear_contrasena(CONTRASENA), rol, empresa_id
        )
        await sesion.commit()
        return usuario.id


async def crear_empresa(codigo: str, nombre: str) -> Empresa:
    async with FabricaSesion() as sesion:
        empresa = Empresa(codigo=codigo, nombre=nombre)
        sesion.add(empresa)
        await sesion.commit()
        return empresa


async def login(cliente: AsyncClient, email: str) -> dict:
    r = await cliente.post("/auth/login", json={"email": email, "contrasena": CONTRASENA})
    assert r.status_code == 200, r.text
    return r.json()


async def cabeceras(cliente: AsyncClient, email: str) -> dict:
    tokens = await login(cliente, email)
    return {"Authorization": f"Bearer {tokens['token_acceso']}"}


class Actores:
    """Un usuario de cada rol, más un segundo usuario y un segundo analista. Los dos usuarios
    son trabajadores de la misma empresa cliente (`empresa`); el personal del MSSP, de ninguna."""

    def __init__(self, ids: dict, cab: dict, empresa: Empresa):
        self.ids = ids
        self.cab = cab
        self.empresa = empresa


@pytest.fixture
async def actores(cliente) -> Actores:
    empresa = await crear_empresa("empresa-pruebas", "Empresa de pruebas")
    emails = {
        "usuario": ("usuario@test.com", Rol.usuario, empresa.id),
        "otro": ("otro@test.com", Rol.usuario, empresa.id),
        "analista": ("analista@test.com", Rol.analista, None),
        "analista2": ("analista2@test.com", Rol.analista, None),
        "admin": ("admin@test.com", Rol.admin, None),
    }
    ids, cab = {}, {}
    for clave, (email, rol, empresa_id) in emails.items():
        ids[clave] = await crear_usuario(email, rol, empresa_id)
        cab[clave] = await cabeceras(cliente, email)
    limitador.reset()
    return Actores(ids, cab, empresa)


INCIDENTE = {
    "titulo": "Correo sospechoso",
    "descripcion": "Recibí un correo pidiendo mis credenciales",
    "severidad": "media",
    "categoria": "phishing",
}


async def crear_incidente(cliente: AsyncClient, cab: dict, **cambios) -> dict:
    r = await cliente.post("/incidentes", json={**INCIDENTE, **cambios}, headers=cab)
    assert r.status_code == 201, r.text
    return r.json()
