from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencias import Admin, IpCliente, Sesion, UsuarioActual
from app.esquemas import (
    AsignacionEntrada,
    CambioEstadoEntrada,
    IncidenteCrear,
    IncidenteEditar,
    IncidenteSalida,
    IncidenteSalidaInterna,
    NotasEntrada,
    Pagina,
)
from app.modelos import Categoria, Estado, Incidente, Severidad, Usuario
from app.servicios import incidentes as servicio

router = APIRouter(prefix="/incidentes", tags=["incidentes"])

Respuesta = IncidenteSalidaInterna | IncidenteSalida


def serializar(usuario: Usuario, incidente: Incidente) -> Respuesta:
    """Elige el esquema de salida según quién pregunta: las notas internas solo salen
    hacia el analista asignado y el admin."""
    if servicio.puede_ver_internas(usuario, incidente):
        return IncidenteSalidaInterna.model_validate(incidente)
    return IncidenteSalida.model_validate(incidente)


@router.post("", response_model=Respuesta, status_code=status.HTTP_201_CREATED)
async def crear(datos: IncidenteCrear, usuario: UsuarioActual, sesion: Sesion, ip: IpCliente):
    return serializar(usuario, await servicio.crear(sesion, usuario, datos, ip))


@router.get("", response_model=Pagina[Respuesta])
async def listar(
    usuario: UsuarioActual,
    sesion: Sesion,
    estado: Estado | None = None,
    severidad: Severidad | None = None,
    categoria: Categoria | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await servicio.listar(
        sesion,
        usuario,
        estado=estado,
        severidad=severidad,
        categoria=categoria,
        limite=limite,
        desplazamiento=desplazamiento,
    )
    return Pagina[Respuesta](
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        elementos=[serializar(usuario, i) for i in elementos],
    )


@router.get("/{incidente_id}", response_model=Respuesta)
async def obtener(incidente_id: int, usuario: UsuarioActual, sesion: Sesion):
    return serializar(usuario, await servicio.obtener(sesion, usuario, incidente_id))


@router.patch("/{incidente_id}", response_model=Respuesta)
async def editar(
    incidente_id: int,
    datos: IncidenteEditar,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    return serializar(usuario, await servicio.editar(sesion, usuario, incidente_id, datos, ip))


@router.patch("/{incidente_id}/estado", response_model=Respuesta)
async def cambiar_estado(
    incidente_id: int,
    datos: CambioEstadoEntrada,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    incidente = await servicio.cambiar_estado(sesion, usuario, incidente_id, datos.estado, ip)
    return serializar(usuario, incidente)


@router.patch("/{incidente_id}/asignar", response_model=Respuesta)
async def asignar(
    incidente_id: int, datos: AsignacionEntrada, admin: Admin, sesion: Sesion, ip: IpCliente
):
    incidente = await servicio.asignar(sesion, admin, incidente_id, datos.analista_id, ip)
    return serializar(admin, incidente)


@router.patch("/{incidente_id}/notas", response_model=Respuesta)
async def actualizar_notas(
    incidente_id: int,
    datos: NotasEntrada,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    incidente = await servicio.actualizar_notas(
        sesion, usuario, incidente_id, datos.notas_internas, ip
    )
    return serializar(usuario, incidente)


@router.delete("/{incidente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(incidente_id: int, admin: Admin, sesion: Sesion, ip: IpCliente) -> None:
    await servicio.borrar(sesion, admin, incidente_id, ip)
