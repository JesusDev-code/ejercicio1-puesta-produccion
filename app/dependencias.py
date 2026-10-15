from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import obtener_sesion
from app.errores import NoAutenticado, Prohibido
from app.identidad import identidad
from app.modelos import Rol, Usuario
from app.repositorios import RepositorioUsuarios
from app.servicios.empresas import cuenta_habilitada

_bearer = HTTPBearer(auto_error=False)

Sesion = Annotated[AsyncSession, Depends(obtener_sesion)]


def ip_cliente(request: Request) -> str | None:
    # Detrás de Traefik, uvicorn reescribe client.host con X-Forwarded-For (--proxy-headers)
    return request.client.host if request.client else None


IpCliente = Annotated[str | None, Depends(ip_cliente)]


async def usuario_actual(
    sesion: Sesion,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Usuario:
    if credenciales is None:
        raise NoAutenticado("No autenticado")
    # Firebase dice QUIÉN es (firma, caducidad, revocación); nuestra BD dice QUÉ puede hacer
    uid = await identidad().verificar(credenciales.credentials)
    if uid is None:
        raise NoAutenticado("Token inválido o caducado")
    # El rol se lee de la BD en cada petición, nunca del token: un cambio de rol es inmediato.
    # Un uid que no está aquí (alguien que se registró solo en Firebase) no entra
    usuario = await RepositorioUsuarios(sesion).por_uid(uid)
    if not usuario or not await cuenta_habilitada(sesion, usuario):
        raise NoAutenticado("Token inválido o caducado")
    return usuario


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


def requiere_rol(*roles: Rol) -> Callable:
    async def comprobar(usuario: UsuarioActual) -> Usuario:
        if usuario.rol not in roles:
            raise Prohibido("Permisos insuficientes")
        return usuario

    return comprobar


Admin = Annotated[Usuario, Depends(requiere_rol(Rol.admin))]
