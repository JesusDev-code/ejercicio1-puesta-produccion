from fastapi import APIRouter, Request, Response, status

from app.config import obtener_configuracion
from app.dependencias import IpCliente, Sesion
from app.errores import NoAutenticado
from app.esquemas import (
    LoginEntrada,
    ParTokens,
    RefrescoEntrada,
    RegistroEntrada,
    RegistroSalida,
    TokenAcceso,
)
from app.limitador import limitador
from app.servicios import auth as servicio
from app.servicios import usuarios as servicio_usuarios

router = APIRouter(prefix="/auth", tags=["auth"])
_limite = obtener_configuracion().limite_auth

# `request` es obligatorio en la firma para que slowapi pueda aplicar el límite


@router.post("/registro", response_model=RegistroSalida, status_code=status.HTTP_201_CREATED)
@limitador.limit(_limite)
async def registro(request: Request, datos: RegistroEntrada, sesion: Sesion, ip: IpCliente):
    """Registro público. Limitado como el login: sin límite, cualquiera crearía miles de
    cuentas o lo usaría para probar qué emails existen."""
    await servicio_usuarios.registrar(sesion, datos.email, datos.contrasena, ip)
    return RegistroSalida()


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


# --- Navegador: el token de refresco vive en una cookie HttpOnly ---
#
# Path acotado (COOKIE_REFRESCO_RUTA): el navegador solo la envía a estas tres rutas.
# SameSite=Strict: una web ajena no puede provocar que el navegador la mande (CSRF).

COOKIE_REFRESCO = "__Secure-refresco"
_SIN_COOKIE = "Falta el token de refresco"


def _poner_cookie(respuesta: Response, token: str) -> None:
    config = obtener_configuracion()
    respuesta.set_cookie(
        COOKIE_REFRESCO,
        token,
        max_age=config.refresco_dias * 86400,
        path=config.cookie_refresco_ruta,
        secure=True,
        httponly=True,
        samesite="strict",
    )


def _solo_acceso(tokens: ParTokens) -> TokenAcceso:
    return TokenAcceso(
        token_acceso=tokens.token_acceso, expira_en_segundos=tokens.expira_en_segundos
    )


@router.post("/web/login", response_model=TokenAcceso)
@limitador.limit(_limite)
async def login_web(
    request: Request, response: Response, datos: LoginEntrada, sesion: Sesion, ip: IpCliente
):
    tokens = await servicio.login(sesion, datos.email, datos.contrasena, ip)
    _poner_cookie(response, tokens.token_refresco)
    return _solo_acceso(tokens)


@router.post("/web/refrescar", response_model=TokenAcceso)
@limitador.limit("30/minute")
async def refrescar_web(request: Request, response: Response, sesion: Sesion, ip: IpCliente):
    token = request.cookies.get(COOKIE_REFRESCO)
    if not token:
        raise NoAutenticado(_SIN_COOKIE)
    tokens = await servicio.refrescar(sesion, token, ip)
    _poner_cookie(response, tokens.token_refresco)
    return _solo_acceso(tokens)


@router.post("/web/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_web(request: Request, response: Response, sesion: Sesion, ip: IpCliente) -> None:
    token = request.cookies.get(COOKIE_REFRESCO)
    if token:
        await servicio.logout(sesion, token, ip)
    response.delete_cookie(
        COOKIE_REFRESCO,
        path=obtener_configuracion().cookie_refresco_ruta,
        secure=True,
        httponly=True,
        samesite="strict",
    )
