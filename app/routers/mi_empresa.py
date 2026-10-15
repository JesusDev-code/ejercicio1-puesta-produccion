"""Lo que ve y gestiona el gestor de una empresa cliente.

La empresa no viene NUNCA de la petición: sale de la cuenta del gestor. No hay ningún id de
empresa que manipular para asomarse a otra.
"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencias import Gestor, IpCliente, Sesion
from app.esquemas import (
    CambioActivoEntrada,
    EmpresaSalida,
    Pagina,
    RestablecerContrasenaEntrada,
    Sensor,
    UsuarioSalida,
)
from app.repositorios import RepositorioUsuarios
from app.servicios import empresas as servicio_empresas
from app.servicios import eventos as servicio_eventos
from app.servicios import usuarios as servicio_usuarios

router = APIRouter(prefix="/mi-empresa", tags=["mi empresa"])


@router.get("", response_model=EmpresaSalida)
async def obtener(gestor: Gestor, sesion: Sesion):
    return await servicio_empresas.obtener(sesion, gestor.empresa_id)


@router.post("/codigo", response_model=EmpresaSalida)
async def regenerar_codigo(gestor: Gestor, sesion: Sesion, ip: IpCliente):
    return await servicio_empresas.regenerar_codigo(sesion, gestor, gestor.empresa_id, ip)


@router.get("/usuarios", response_model=Pagina[UsuarioSalida])
async def listar_usuarios(
    gestor: Gestor,
    sesion: Sesion,
    email: Annotated[str | None, Query(max_length=254)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioUsuarios(sesion).listar(
        limite, desplazamiento, email=email, empresa_id=gestor.empresa_id
    )
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.patch("/usuarios/{usuario_id}/activo", response_model=UsuarioSalida)
async def cambiar_activo(
    usuario_id: int, datos: CambioActivoEntrada, gestor: Gestor, sesion: Sesion, ip: IpCliente
):
    return await servicio_usuarios.cambiar_activo(sesion, gestor, usuario_id, datos.activo, ip)


@router.patch("/usuarios/{usuario_id}/contrasena", status_code=status.HTTP_204_NO_CONTENT)
async def restablecer_contrasena(
    usuario_id: int,
    datos: RestablecerContrasenaEntrada,
    gestor: Gestor,
    sesion: Sesion,
    ip: IpCliente,
) -> None:
    await servicio_usuarios.restablecer_contrasena(
        sesion, gestor, usuario_id, datos.contrasena_nueva, ip
    )


@router.get("/sensores", response_model=list[Sensor])
async def sensores(gestor: Gestor, sesion: Sesion):
    return await servicio_eventos.sensores(sesion, gestor.empresa_id)
