from fastapi import APIRouter, Request, status

from app.config import obtener_configuracion
from app.dependencias import IpCliente, Sesion
from app.esquemas import LoginEntrada, ParTokens, RefrescoEntrada, RegistroEntrada, UsuarioSalida
from app.limitador import limitador
from app.servicios import auth as servicio

router = APIRouter(prefix="/auth", tags=["auth"])
_limite = obtener_configuracion().limite_auth

# `request` es obligatorio en la firma para que slowapi pueda aplicar el límite


@router.post("/registro", response_model=UsuarioSalida, status_code=status.HTTP_201_CREATED)
@limitador.limit(_limite)
async def registro(request: Request, datos: RegistroEntrada, sesion: Sesion, ip: IpCliente):
    return await servicio.registrar(sesion, datos.email, datos.contrasena, ip)


@router.post("/login", response_model=ParTokens)
@limitador.limit(_limite)
async def login(request: Request, datos: LoginEntrada, sesion: Sesion, ip: IpCliente):
    return await servicio.login(sesion, datos.email, datos.contrasena, ip)


@router.post("/refrescar", response_model=ParTokens)
@limitador.limit("30/minute")
async def refrescar(request: Request, datos: RefrescoEntrada, sesion: Sesion, ip: IpCliente):
    return await servicio.refrescar(sesion, datos.token_refresco, ip)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(datos: RefrescoEntrada, sesion: Sesion, ip: IpCliente) -> None:
    await servicio.logout(sesion, datos.token_refresco, ip)
