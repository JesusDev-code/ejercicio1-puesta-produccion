"""Siembra para los E2E: dos clientes, un admin y un trabajador de cada cliente.

Lo lanza frontend/web/e2e/entorno.mjs contra una BD desechable. Se niega a correr con
ENTORNO=produccion: estas cuentas tienen una contraseña conocida y publicada en el repo.
Las credenciales tienen que coincidir con frontend/web/e2e/datos.mjs.
"""

import asyncio
import sys

from app.config import obtener_configuracion
from app.db import FabricaSesion
from app.modelos import Empresa, Rol
from app.repositorios import RepositorioUsuarios
from app.seguridad import hashear_contrasena

CONTRASENA = "contrasena-e2e-segura"

EMPRESAS = [
    ("transportes-ibarra", "Transportes Ibarra", "Logística"),
    ("clinica-solana", "Clínica Solana", "Sanidad"),
]

CUENTAS = [
    ("admin@kaelum.example.com", Rol.admin, None),
    ("ana@ibarra.example.com", Rol.usuario, "transportes-ibarra"),
    ("luis@solana.example.com", Rol.usuario, "clinica-solana"),
]


async def sembrar() -> None:
    async with FabricaSesion() as sesion:
        ids: dict[str, int] = {}
        for codigo, nombre, sector in EMPRESAS:
            empresa = Empresa(codigo=codigo, nombre=nombre, sector=sector)
            sesion.add(empresa)
            await sesion.flush()
            ids[codigo] = empresa.id
        repo = RepositorioUsuarios(sesion)
        for email, rol, empresa in CUENTAS:
            await repo.crear(
                email, hashear_contrasena(CONTRASENA), rol, ids[empresa] if empresa else None
            )
        await sesion.commit()


if __name__ == "__main__":
    if obtener_configuracion().es_produccion:
        sys.exit("La semilla E2E no se ejecuta en producción")
    asyncio.run(sembrar())
    print("Semilla E2E lista")
