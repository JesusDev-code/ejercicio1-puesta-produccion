from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import obtener_sesion
from app.errores import NoAutenticado, Prohibido
from app.modelos import Rol, Usuario
from app.repositorios import RepositorioUsuarios
from app.seguridad import decodificar_token_acceso

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
    usuario_id = decodificar_token_acceso(credenciales.credentials)
    if usuario_id is None:
        raise NoAutenticado("Token inválido o caducado")
    # El rol se lee de la BD en cada petición, nunca del token: un cambio de rol es inmediato
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario or not usuario.activo:
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
