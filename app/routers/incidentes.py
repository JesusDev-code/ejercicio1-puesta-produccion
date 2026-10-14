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


def serializar(usuario: Usuario, incidente: Incidente, emails: dict[int, str]) -> Respuesta:
    """Elige el esquema de salida según quién pregunta: las notas internas solo salen
    hacia el analista asignado y el admin."""
    esquema = (
        IncidenteSalidaInterna
        if servicio.puede_ver_internas(usuario, incidente)
        else IncidenteSalida
    )
    salida = esquema.model_validate(incidente)
    salida.reportante_email = emails.get(incidente.reportante_id)
    salida.analista_email = emails.get(incidente.analista_id) if incidente.analista_id else None
    return salida


async def responder(sesion: Sesion, usuario: Usuario, incidente: Incidente) -> Respuesta:
    return serializar(usuario, incidente, await servicio.emails_de(sesion, [incidente]))


@router.post("", response_model=Respuesta, status_code=status.HTTP_201_CREATED)
async def crear(datos: IncidenteCrear, usuario: UsuarioActual, sesion: Sesion, ip: IpCliente):
    return await responder(sesion, usuario, await servicio.crear(sesion, usuario, datos, ip))


@router.get("", response_model=Pagina[Respuesta])
async def listar(
    usuario: UsuarioActual,
    sesion: Sesion,
    estado: Estado | None = None,
    severidad: Severidad | None = None,
    categoria: Categoria | None = None,
    empresa_id: Annotated[int | None, Query(gt=0)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await servicio.listar(
        sesion,
        usuario,
        empresa_id=empresa_id,
        estado=estado,
        severidad=severidad,
        categoria=categoria,
        limite=limite,
        desplazamiento=desplazamiento,
    )
    emails = await servicio.emails_de(sesion, elementos)
    return Pagina[Respuesta](
        total=total,
        limite=limite,
        desplazamiento=desplazamiento,
        elementos=[serializar(usuario, i, emails) for i in elementos],
    )


@router.get("/{incidente_id}", response_model=Respuesta)
async def obtener(incidente_id: int, usuario: UsuarioActual, sesion: Sesion):
    return await responder(sesion, usuario, await servicio.obtener(sesion, usuario, incidente_id))


@router.patch("/{incidente_id}", response_model=Respuesta)
async def editar(
    incidente_id: int,
    datos: IncidenteEditar,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    incidente = await servicio.editar(sesion, usuario, incidente_id, datos, ip)
    return await responder(sesion, usuario, incidente)


@router.patch("/{incidente_id}/estado", response_model=Respuesta)
async def cambiar_estado(
    incidente_id: int,
    datos: CambioEstadoEntrada,
    usuario: UsuarioActual,
    sesion: Sesion,
    ip: IpCliente,
):
    incidente = await servicio.cambiar_estado(sesion, usuario, incidente_id, datos.estado, ip)
    return await responder(sesion, usuario, incidente)


@router.patch("/{incidente_id}/asignar", response_model=Respuesta)
async def asignar(
    incidente_id: int, datos: AsignacionEntrada, admin: Admin, sesion: Sesion, ip: IpCliente
):
    incidente = await servicio.asignar(sesion, admin, incidente_id, datos.analista_id, ip)
    return await responder(sesion, admin, incidente)


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
    return await responder(sesion, usuario, incidente)


@router.delete("/{incidente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(incidente_id: int, admin: Admin, sesion: Sesion, ip: IpCliente) -> None:
    await servicio.borrar(sesion, admin, incidente_id, ip)
