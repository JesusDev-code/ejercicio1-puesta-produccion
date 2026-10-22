import hmac

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import obtener_configuracion
from app.dependencias import IpCliente, Sesion
from app.errores import Conflicto, NoAutenticado
from app.esquemas import (
    DesafioMfa,
    LoginEntrada,
    MfaEntrada,
    ParTokens,
    ProveedoresOAuth,
    RefrescoEntrada,
    RegistroEntrada,
    RegistroSalida,
    TokenAcceso,
)
from app.limitador import limitador
from app.repositorios import RepositorioUsuarios
from app.seguridad import crear_estado_oauth, decodificar_estado_oauth
from app.servicios import auth as servicio
from app.servicios import oauth as servicio_oauth
from app.servicios import usuarios as servicio_usuarios
from app.servicios.auditoria import auditar
from app.servicios.empresas import cuenta_habilitada

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


@router.post("/login", response_model=ParTokens | DesafioMfa)
@limitador.limit(_limite)
async def login(request: Request, datos: LoginEntrada, sesion: Sesion, ip: IpCliente):
    """Sin MFA, los tokens. Con MFA, un desafío que se canjea en /auth/mfa."""
    return await servicio.login(sesion, datos.email, datos.contrasena, ip)


@router.post("/mfa", response_model=ParTokens)
@limitador.limit(_limite)
async def mfa(request: Request, datos: MfaEntrada, sesion: Sesion, ip: IpCliente):
    return await servicio.completar_mfa(sesion, datos.desafio, datos.codigo, ip)


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


@router.post("/web/login", response_model=TokenAcceso | DesafioMfa)
@limitador.limit(_limite)
async def login_web(
    request: Request, response: Response, datos: LoginEntrada, sesion: Sesion, ip: IpCliente
):
    resultado = await servicio.login(sesion, datos.email, datos.contrasena, ip)
    if isinstance(resultado, DesafioMfa):
        return resultado
    _poner_cookie(response, resultado.token_refresco)
    return _solo_acceso(resultado)


@router.post("/web/mfa", response_model=TokenAcceso)
@limitador.limit(_limite)
async def mfa_web(
    request: Request, response: Response, datos: MfaEntrada, sesion: Sesion, ip: IpCliente
):
    tokens = await servicio.completar_mfa(sesion, datos.desafio, datos.codigo, ip)
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


# --- Login con Google y GitHub (OAuth 2.0 + PKCE) ---
#
# La cookie del flujo es SameSite=Lax, no Strict: la vuelta desde el proveedor es una navegación
# que viene de otro sitio, y con Strict el navegador no la mandaría. Solo viaja a /auth/oauth
# y dura 10 minutos.

COOKIE_OAUTH = "__Secure-oauth"


def poner_cookie_oauth(respuesta: Response, valor: str) -> None:
    respuesta.set_cookie(
        COOKIE_OAUTH,
        valor,
        max_age=600,
        path=obtener_configuracion().cookie_oauth_ruta,
        secure=True,
        httponly=True,
        samesite="lax",
    )


def iniciar_oauth(
    respuesta: Response, proveedor: str, vincular_a: tuple[int, int] | None = None
) -> str:
    """Prepara la ida al proveedor: deja state + PKCE en la cookie y devuelve la URL."""
    prov = servicio_oauth.proveedores().get(proveedor)
    if not prov:
        raise Conflicto("Ese proveedor no está disponible")
    url, estado, verificador = servicio_oauth.url_autorizacion(prov)
    poner_cookie_oauth(respuesta, crear_estado_oauth(proveedor, estado, verificador, vincular_a))
    return url


def _url_front(ruta: str) -> str:
    return f"{obtener_configuracion().url_publica}{ruta}"


@router.get("/oauth/proveedores", response_model=ProveedoresOAuth)
async def proveedores_oauth():
    """Los que están configurados: el front solo pinta esos botones."""
    return ProveedoresOAuth(proveedores=list(servicio_oauth.proveedores()))


@router.get("/oauth/{proveedor}/inicio")
@limitador.limit("10/minute")
async def oauth_inicio(request: Request, proveedor: str):
    respuesta = RedirectResponse(_url_front("/login?error=oauth"), status_code=302)
    try:
        respuesta.headers["location"] = iniciar_oauth(respuesta, proveedor)
    except Conflicto:
        pass
    return respuesta


@router.get("/oauth/{proveedor}/callback")
@limitador.limit("20/minute")
async def oauth_callback(
    request: Request,
    proveedor: str,
    sesion: Sesion,
    ip: IpCliente,
    code: str | None = None,
    state: str | None = None,
):
    guardado = request.cookies.get(COOKIE_OAUTH)
    datos = decodificar_estado_oauth(guardado) if guardado else None
    vinculando = datos is not None and "sub" in datos
    prov = servicio_oauth.proveedores().get(proveedor)

    try:
        # El `state` de la URL tiene que ser el de la cookie de ESTE navegador. Si no, alguien
        # intenta colar su propio código para que la víctima acabe dentro de la cuenta del
        # atacante (login CSRF). Sin code ni state: el usuario canceló en el proveedor
        if (
            not prov
            or not datos
            or datos["prov"] != proveedor
            or not code
            or not state
            or not hmac.compare_digest(datos["st"], state)
        ):
            if code or state:
                await auditar(
                    sesion,
                    accion="oauth_estado_invalido",
                    recurso="usuario",
                    usuario_id=None,
                    ip=ip,
                    detalle=proveedor[:20],
                )
                await sesion.commit()
            raise NoAutenticado("Estado OAuth inválido")

        perfil = await servicio_oauth.obtener_perfil(prov, code, datos["pkce"])

        if vinculando:
            usuario = await RepositorioUsuarios(sesion).por_id(int(datos["sub"]))
            if (
                not usuario
                or usuario.version_sesion != datos["ver"]
                or not await cuenta_habilitada(sesion, usuario)
            ):
                raise NoAutenticado("Sesión caducada")
            await servicio_oauth.vincular(sesion, usuario, proveedor, perfil, ip)
            respuesta = RedirectResponse(_url_front(f"/cuenta?vinculado={proveedor}"), 302)
        else:
            usuario = await servicio_oauth.resolver_usuario(sesion, proveedor, perfil, ip)
            resultado = await servicio.iniciar_sesion(sesion, usuario, ip, metodo=proveedor)
            if isinstance(resultado, DesafioMfa):
                # En el fragmento: no viaja al servidor ni queda en los logs de los proxies
                respuesta = RedirectResponse(_url_front(f"/login#mfa={resultado.desafio}"), 302)
            else:
                respuesta = RedirectResponse(_url_front("/"), 302)
                _poner_cookie(respuesta, resultado.token_refresco)
    except servicio_oauth.EmailYaRegistrado:
        respuesta = RedirectResponse(_url_front("/login?error=oauth_email"), 302)
    except (NoAutenticado, Conflicto):
        destino = "/cuenta?error_vinculo=1" if vinculando else "/login?error=oauth"
        respuesta = RedirectResponse(_url_front(destino), 302)

    # Un solo uso: la cookie del flujo se borra salga bien o mal
    respuesta.delete_cookie(
        COOKIE_OAUTH,
        path=obtener_configuracion().cookie_oauth_ruta,
        secure=True,
        httponly=True,
        samesite="lax",
    )
    return respuesta
