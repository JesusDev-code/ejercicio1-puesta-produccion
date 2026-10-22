import asyncio
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.config import obtener_configuracion
from app.db import FabricaSesion
from app.dependencias import Admin, IpCliente, Sesion, _bearer, identificacion, usuario_operativo
from app.errores import NoAutenticado, NoEncontrado, Prohibido
from app.esquemas import (
    EventoSalida,
    IncidenteSalidaInterna,
    LoteEventos,
    Pagina,
    ResumenEventos,
    Sensor,
    TriajeEntrada,
)
from app.modelos import EstadoTriaje, Rol, Severidad, TipoEvento
from app.servicios import eventos as servicio
from app.tiempo_real import difusor

router = APIRouter(prefix="/eventos", tags=["eventos"])

# Un panel abierto se reconecta cada 10 minutos: así vuelve a pasar la autenticación con un
# token vigente y una pestaña olvidada no queda escuchando para siempre
DURACION_STREAM = 600
LATIDO = 15


async def token_ingesta(x_ingesta_token: Annotated[str | None, Header()] = None) -> None:
    esperado = obtener_configuracion().ingesta_token
    if not esperado:
        raise Prohibido("Ingesta desactivada")
    # Comparación en tiempo constante: no filtra cuántos caracteres coinciden
    if not x_ingesta_token or not secrets.compare_digest(x_ingesta_token, esperado):
        raise NoAutenticado("Token de ingesta inválido")


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(token_ingesta)])
async def ingestar(lote: LoteEventos, sesion: Sesion) -> dict[str, int]:
    return {"recibidos": await servicio.ingestar(sesion, lote.eventos)}


@router.get("", response_model=Pagina[EventoSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    tipo: TipoEvento | None = None,
    severidad: Severidad | None = None,
    origen_ip: Annotated[str | None, Query(max_length=45)] = None,
    estado: EstadoTriaje | None = None,
    empresa_id: Annotated[int | None, Query(gt=0)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 25,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await servicio.listar(
        sesion,
        tipo=tipo,
        severidad=severidad,
        origen_ip=origen_ip,
        estado=estado,
        empresa_id=empresa_id,
        limite=limite,
        desplazamiento=desplazamiento,
    )
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.get("/por-incidente/{incidente_id}", response_model=EventoSalida)
async def por_incidente(incidente_id: int, _: Admin, sesion: Sesion):
    evento = await servicio.evento_por_incidente(sesion, incidente_id)
    if not evento:
        raise NoEncontrado("Esta incidencia no procede de un evento")
    return evento


@router.get("/resumen", response_model=ResumenEventos)
async def resumen(
    _: Admin,
    sesion: Sesion,
    horas: Annotated[int, Query(ge=1, le=168)] = 24,
    empresa_id: Annotated[int | None, Query(gt=0)] = None,
):
    return await servicio.resumen(sesion, horas, empresa_id)


@router.get("/sensores", response_model=list[Sensor])
async def sensores(_: Admin, sesion: Sesion):
    return await servicio.sensores(sesion)


@router.patch("/{evento_id}", response_model=EventoSalida)
async def triar(evento_id: int, datos: TriajeEntrada, admin: Admin, sesion: Sesion, ip: IpCliente):
    return await servicio.triar(sesion, admin, evento_id, datos, ip)


async def _admin_breve(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Como `Admin`, pero con una sesión de BD que se cierra al momento: el stream dura
    minutos y no debe retener una conexión del pool mientras tanto."""
    async with FabricaSesion() as sesion:
        usuario = (await identificacion(sesion, credenciales)).usuario
    # Las mismas barreras que `Admin`: un admin sin MFA activado tampoco ve el stream
    await usuario_operativo(usuario)
    if usuario.rol != Rol.admin:
        raise Prohibido("Permisos insuficientes")


@router.get("/stream", dependencies=[Depends(_admin_breve)])
async def stream(request: Request) -> StreamingResponse:
    cola = difusor.suscribir()

    async def emitir():
        fin = time.monotonic() + DURACION_STREAM
        try:
            yield "retry: 3000\n\n"
            while time.monotonic() < fin:
                if await request.is_disconnected():
                    return
                try:
                    dato = await asyncio.wait_for(cola.get(), timeout=LATIDO)
                    yield f"data: {dato}\n\n"
                except TimeoutError:
                    # Comentario SSE: mantiene viva la conexión a través de los proxies
                    yield ": latido\n\n"
            yield "event: fin\ndata: {}\n\n"
        finally:
            difusor.baja(cola)

    return StreamingResponse(
        emitir(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{evento_id}/incidente",
    response_model=IncidenteSalidaInterna,
    status_code=status.HTTP_201_CREATED,
)
async def crear_incidente(evento_id: int, admin: Admin, sesion: Sesion, ip: IpCliente):
    incidente = await servicio.crear_incidente(sesion, admin, evento_id, ip)
    salida = IncidenteSalidaInterna.model_validate(incidente)
    salida.reportante_email = admin.email
    return salida
