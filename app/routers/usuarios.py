from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.config import obtener_configuracion
from app.dependencias import Admin, IpCliente, Sesion, UsuarioActual
from app.esquemas import (
    CambioActivoEntrada,
    CambioContrasenaEntrada,
    CambioRolEntrada,
    Pagina,
    UsuarioSalida,
)
from app.limitador import limitador
from app.modelos import Rol
from app.repositorios import RepositorioUsuarios
from app.servicios import usuarios as servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
_limite = obtener_configuracion().limite_auth


@router.get("/yo", response_model=UsuarioSalida)
async def yo(usuario: UsuarioActual):
    return usuario


# `request` es obligatorio en la firma para que slowapi pueda aplicar el límite.
# Se limita igual que el login: verifica una contraseña, así que es un oráculo de fuerza bruta.
@router.patch("/yo/contrasena", status_code=status.HTTP_204_NO_CONTENT)
@limitador.limit(_limite)
async def cambiar_contrasena(
    request: Request,
    datos: CambioContrasenaEntrada,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
) -> None:
    await servicio.cambiar_contrasena(
        sesion, usuario, datos.contrasena_actual, datos.contrasena_nueva, ip
    )


@router.get("", response_model=Pagina[UsuarioSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    rol: Rol | None = None,
    email: Annotated[str | None, Query(max_length=254)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioUsuarios(sesion).listar(
        limite, desplazamiento, rol=rol, email=email
    )
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.patch("/{usuario_id}/rol", response_model=UsuarioSalida)
async def cambiar_rol(
    usuario_id: int, datos: CambioRolEntrada, admin: Admin, sesion: Sesion, ip: IpCliente
):
    return await servicio.cambiar_rol(sesion, admin, usuario_id, datos.rol, ip)


@router.patch("/{usuario_id}/activo", response_model=UsuarioSalida)
async def cambiar_activo(
    usuario_id: int, datos: CambioActivoEntrada, admin: Admin, sesion: Sesion, ip: IpCliente
):
    return await servicio.cambiar_activo(sesion, admin, usuario_id, datos.activo, ip)
