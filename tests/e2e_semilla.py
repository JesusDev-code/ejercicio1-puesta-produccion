"""Siembra para los E2E: dos clientes, un admin y un trabajador de cada cliente.

Crea las cuentas en el EMULADOR de Firebase Auth y en la BD. Lo lanza frontend/web/e2e/entorno.mjs;
negarse a correr sin emulador evita crear cuentas de prueba en el proyecto real.
Las credenciales tienen que coincidir con frontend/web/e2e/datos.ts.
"""

import asyncio
import os
import sys

from app.db import FabricaSesion
from app.identidad import identidad
from app.modelos import Empresa, Rol
from app.repositorios import RepositorioUsuarios

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
            uid = await identidad().crear(email, CONTRASENA)
            await repo.crear(email, uid, rol, ids[empresa] if empresa else None)
        await sesion.commit()


if __name__ == "__main__":
    if not os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        sys.exit("Solo contra el emulador de Firebase Auth (FIREBASE_AUTH_EMULATOR_HOST)")
    asyncio.run(sembrar())
    print("Semilla E2E lista")
