from typing import Annotated

from fastapi import APIRouter, Query, Request, status

from app.config import obtener_configuracion
from app.dependencias import Admin, IpCliente, Sesion, UsuarioActual
from app.esquemas import (
    CambioActivoEntrada,
    CambioContrasenaEntrada,
    CambioRolEntrada,
    Pagina,
    RestablecerContrasenaEntrada,
    UnirseEmpresaEntrada,
    UsuarioCrear,
    UsuarioSalida,
    UsuarioYo,
)
from app.limitador import limitador
from app.modelos import Rol, Usuario
from app.repositorios import RepositorioUsuarios
from app.servicios import usuarios as servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
_limite = obtener_configuracion().limite_auth


async def _perfil(sesion, usuario: Usuario) -> UsuarioYo:
    nombre = await servicio.nombre_empresa(sesion, usuario)
    return UsuarioYo.model_validate(usuario).model_copy(update={"empresa_nombre": nombre})


@router.get("/yo", response_model=UsuarioYo)
async def yo(usuario: UsuarioActual, sesion: Sesion):
    return await _perfil(sesion, usuario)


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


# Limitado como el login: es lo único que protege el código de invitación de la fuerza bruta
@router.post("/yo/empresa", response_model=UsuarioYo)
@limitador.limit(_limite)
async def unirse_a_empresa(
    request: Request,
    datos: UnirseEmpresaEntrada,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    unido = await servicio.unirse_a_empresa(sesion, usuario, datos.codigo, ip)
    return await _perfil(sesion, unido)


@router.get("", response_model=Pagina[UsuarioSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    rol: Rol | None = None,
    email: Annotated[str | None, Query(max_length=254)] = None,
    empresa_id: Annotated[int | None, Query(gt=0)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioUsuarios(sesion).listar(
        limite, desplazamiento, rol=rol, email=email, empresa_id=empresa_id
    )
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.post("", response_model=UsuarioSalida, status_code=status.HTTP_201_CREATED)
async def crear(datos: UsuarioCrear, admin: Admin, sesion: Sesion, ip: IpCliente):
    return await servicio.crear(
        sesion, admin, datos.email, datos.contrasena, datos.rol, datos.empresa_id, ip
    )


@router.patch("/{usuario_id}/contrasena", status_code=status.HTTP_204_NO_CONTENT)
async def restablecer_contrasena(
    usuario_id: int,
    datos: RestablecerContrasenaEntrada,
    admin: Admin,
    sesion: Sesion,
    ip: IpCliente,
) -> None:
    await servicio.restablecer_contrasena(sesion, admin, usuario_id, datos.contrasena_nueva, ip)


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
