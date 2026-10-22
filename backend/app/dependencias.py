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
from app.servicios.empresas import cuenta_habilitada
from app.servicios.mfa import mfa_por_activar

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
    datos = decodificar_token_acceso(credenciales.credentials)
    if datos is None:
        raise NoAutenticado("Token inválido o caducado")
    usuario_id, version = datos
    # El rol se lee de la BD en cada petición, nunca del token: un cambio de rol es inmediato
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario or not await cuenta_habilitada(sesion, usuario):
        raise NoAutenticado("Token inválido o caducado")
    # Token emitido antes de un cambio de contraseña, rol o baja: revocado aunque no haya caducado
    if version != usuario.version_sesion:
        raise NoAutenticado("Token inválido o caducado")
    return usuario


UsuarioActual = Annotated[Usuario, Depends(usuario_actual)]


async def usuario_operativo(usuario: UsuarioActual) -> Usuario:
    """Cualquier cuenta salvo una pendiente (recién registrada y sin empresa todavía) o una de
    personal que aún no ha activado el MFA. Esas solo pueden ver su cuenta y completar lo que
    les falta (eso va con `UsuarioActual`)."""
    if usuario.pendiente:
        raise Prohibido("Únete primero a tu empresa con su código de invitación")
    # Personal del MSSP sin MFA: con su contraseña sola no ve datos de ningún cliente
    if mfa_por_activar(usuario):
        raise Prohibido("Activa la verificación en dos pasos para continuar")
    return usuario


UsuarioOperativo = Annotated[Usuario, Depends(usuario_operativo)]


def requiere_rol(*roles: Rol) -> Callable:
    async def comprobar(usuario: UsuarioOperativo) -> Usuario:
        if usuario.rol not in roles:
            raise Prohibido("Permisos insuficientes")
        return usuario

    return comprobar


Admin = Annotated[Usuario, Depends(requiere_rol(Rol.admin))]
# Pasa por UsuarioOperativo: un gestor siempre tiene empresa cuando llega aquí
Gestor = Annotated[Usuario, Depends(requiere_rol(Rol.gestor))]
