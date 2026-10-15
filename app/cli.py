"""Uso: python -m app.cli crear-admin <email>
     python -m app.cli sembrar-demo


La contraseña se pide por consola y no queda en el historial ni en ningún fichero.
La cuenta se crea (o se actualiza) en Firebase y aquí; si el email ya existe, se asciende a
admin y se le pone la contraseña nueva. Un admin es personal de Kaelum: se le quita la empresa."""

import argparse
import asyncio
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.db import FabricaSesion
from app.demo import sembrar_demo
from app.identidad import identidad
from app.modelos import Empresa, Rol
from app.repositorios import RepositorioUsuarios
from app.servicios.auditoria import auditar


async def crear_admin(email: str, contrasena: str) -> None:
    async with FabricaSesion() as sesion:
        usuarios = RepositorioUsuarios(sesion)
        uid = await identidad().buscar(email)
        if uid:
            await identidad().cambiar_contrasena(uid, contrasena)
            await identidad().activar(uid, True)
            await identidad().revocar(uid)
        else:
            uid = await identidad().crear(email, contrasena)
        usuario = await usuarios.por_email(email)
        if usuario:
            usuario.rol = Rol.admin
            usuario.empresa_id = None
            usuario.activo = True
            usuario.firebase_uid = uid
        else:
            usuario = await usuarios.crear(email, uid, Rol.admin)
        await auditar(
            sesion,
            accion="crear_admin_cli",
            recurso="usuario",
            usuario_id=None,
            recurso_id=usuario.id,
            detalle=email,
        )
        await sesion.commit()


async def _sembrar() -> None:
    async with FabricaSesion() as sesion:
        hecho = await sembrar_demo(sesion)
        codigos = list(await sesion.scalars(select(Empresa.codigo).order_by(Empresa.codigo)))
    # Con datos previos solo se completan las empresas: se dice, para no confundir
    print(
        "Datos de demo creados"
        if hecho
        else "Ya había datos de demo: solo se completan las empresas"
    )
    print(f"Empresas: {', '.join(codigos) or 'ninguna'}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("crear-admin").add_argument("email")
    sub.add_parser("sembrar-demo", help="Datos ficticios para enseñar la aplicación")
    args = parser.parse_args()

    if args.comando == "sembrar-demo":
        asyncio.run(_sembrar())
        return

    try:
        email = TypeAdapter(EmailStr).validate_python(args.email)
    except ValidationError:
        sys.exit("Email no válido")

    contrasena = getpass.getpass("Contraseña (mín. 12): ")
    if len(contrasena) < 12 or len(contrasena) > 128:
        sys.exit("La contraseña debe tener entre 12 y 128 caracteres")
    if getpass.getpass("Repite la contraseña: ") != contrasena:
        sys.exit("Las contraseñas no coinciden")

    asyncio.run(crear_admin(email, contrasena))
    print(f"Admin listo: {email}")


if __name__ == "__main__":
    main()
