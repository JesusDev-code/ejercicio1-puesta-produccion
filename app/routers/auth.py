from fastapi import APIRouter, status

from app.dependencias import IpCliente, Sesion, UsuarioActual
from app.servicios import auth as servicio

# El login lo hace el navegador contra Firebase. Estas rutas solo dejan rastro en la auditoría.
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sesion", status_code=status.HTTP_204_NO_CONTENT)
async def entrada(usuario: UsuarioActual, sesion: Sesion, ip: IpCliente) -> None:
    await servicio.registrar_entrada(sesion, usuario, ip)


@router.post("/salida", status_code=status.HTTP_204_NO_CONTENT)
async def salida(usuario: UsuarioActual, sesion: Sesion, ip: IpCliente) -> None:
    await servicio.registrar_salida(sesion, usuario, ip)
