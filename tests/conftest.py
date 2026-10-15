import os

# La configuración se lee al importar la app: el entorno se fija antes de cualquier import
os.environ["ENTORNO"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite://")
os.environ["CORS_ORIGENES"] = "https://app.ejemplo.com"

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app import identidad  # noqa: E402
from app.db import Base, FabricaSesion, motor  # noqa: E402
from app.limitador import limitador  # noqa: E402
from app.main import app  # noqa: E402
from app.modelos import Rol  # noqa: E402
from app.repositorios import RepositorioUsuarios  # noqa: E402

CONTRASENA = "contrasena-segura-123"


class IdentidadFalsa:
    """Firebase de mentira, en memoria. Emite tokens `falso:<uid>:<generación>`; revocar sube la
    generación, así los tokens anteriores dejan de valer igual que con `check_revoked`."""

    def __init__(self):
        self.cuentas: dict[str, dict] = {}

    def _uid(self, email: str) -> str | None:
        return next((u for u, c in self.cuentas.items() if c["email"] == email.lower()), None)

    async def verificar(self, token: str) -> str | None:
        partes = token.split(":")
        if len(partes) != 3 or partes[0] != "falso" or partes[1] not in self.cuentas:
            return None
        cuenta = self.cuentas[partes[1]]
        if not cuenta["activo"] or partes[2] != str(cuenta["generacion"]):
            return None
        return partes[1]

    async def crear(self, email: str, contrasena: str) -> str:
        if self._uid(email):
            raise identidad.EmailYaRegistrado(email)
        uid = f"uid-{len(self.cuentas) + 1}"
        self.cuentas[uid] = {
            "email": email.lower(),
            "contrasena": contrasena,
            "activo": True,
            "generacion": 0,
        }
        return uid

    async def buscar(self, email: str) -> str | None:
        return self._uid(email)

    async def comprobar_contrasena(self, email: str, contrasena: str) -> bool:
        uid = self._uid(email)
        return bool(uid) and self.cuentas[uid]["contrasena"] == contrasena

    async def cambiar_contrasena(self, uid: str, nueva: str) -> None:
        self.cuentas[uid]["contrasena"] = nueva

    async def activar(self, uid: str, activo: bool) -> None:
        self.cuentas[uid]["activo"] = activo

    async def revocar(self, uid: str) -> None:
        self.cuentas[uid]["generacion"] += 1

    def iniciar_sesion(self, email: str, contrasena: str) -> str | None:
        """Lo que hace el navegador con signInWithEmailAndPassword."""
        uid = self._uid(email)
        if not uid or not self.cuentas[uid]["activo"]:
            return None
        if self.cuentas[uid]["contrasena"] != contrasena:
            return None
        return f"falso:{uid}:{self.cuentas[uid]['generacion']}"


@pytest.fixture(autouse=True)
def falsa() -> IdentidadFalsa:
    proveedor = IdentidadFalsa()
    identidad.establecer(proveedor)
    yield proveedor
    identidad.establecer(None)


def proveedor() -> IdentidadFalsa:
    return identidad.identidad()  # type: ignore[return-value]


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


async def crear_usuario(email: str, rol: Rol = Rol.usuario) -> int:
    uid = await proveedor().crear(email, CONTRASENA)
    async with FabricaSesion() as sesion:
        usuario = await RepositorioUsuarios(sesion).crear(email, uid, rol)
        await sesion.commit()
        return usuario.id


async def cabeceras(cliente: AsyncClient, email: str, contrasena: str = CONTRASENA) -> dict:
    """Login como el front: credenciales contra «Firebase» y aviso a la API (auditoría)."""
    token = proveedor().iniciar_sesion(email, contrasena)
    assert token, f"Firebase rechazaría el login de {email}"
    cab = {"Authorization": f"Bearer {token}"}
    r = await cliente.post("/auth/sesion", headers=cab)
    assert r.status_code == 204, r.text
    return cab


class Actores:
    """Un usuario de cada rol, más un segundo usuario y un segundo analista."""

    def __init__(self, ids: dict, cab: dict):
        self.ids = ids
        self.cab = cab


@pytest.fixture
async def actores(cliente) -> Actores:
    emails = {
        "usuario": ("usuario@test.com", Rol.usuario),
        "otro": ("otro@test.com", Rol.usuario),
        "analista": ("analista@test.com", Rol.analista),
        "analista2": ("analista2@test.com", Rol.analista),
        "admin": ("admin@test.com", Rol.admin),
    }
    ids, cab = {}, {}
    for clave, (email, rol) in emails.items():
        ids[clave] = await crear_usuario(email, rol)
        cab[clave] = await cabeceras(cliente, email)
    limitador.reset()
    return Actores(ids, cab)


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
