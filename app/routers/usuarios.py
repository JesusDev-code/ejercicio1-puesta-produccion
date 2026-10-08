from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencias import Admin, IpCliente, Sesion, UsuarioActual
from app.esquemas import CambioRolEntrada, Pagina, UsuarioSalida
from app.repositorios import RepositorioUsuarios
from app.servicios import usuarios as servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/yo", response_model=UsuarioSalida)
async def yo(usuario: UsuarioActual):
    return usuario


@router.get("", response_model=Pagina[UsuarioSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioUsuarios(sesion).listar(limite, desplazamiento)
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.patch("/{usuario_id}/rol", response_model=UsuarioSalida)
async def cambiar_rol(
    usuario_id: int, datos: CambioRolEntrada, admin: Admin, sesion: Sesion, ip: IpCliente
):
    return await servicio.cambiar_rol(sesion, admin, usuario_id, datos.rol, ip)
