"""Login con Google y GitHub: OAuth 2.0 Authorization Code con PKCE, resuelto en el backend.

El navegador nunca ve un token del proveedor. La API canjea el código, lee la identidad y
emite SU propia sesión (la misma cookie de refresco que el login con contraseña).

Reglas:
1. La identidad se busca por (proveedor, sujeto), nunca por email.
2. Una cuenta nueva solo nace de un email que el proveedor dé por VERIFICADO, y nace como en el
   registro público: rol usuario, sin empresa, pendiente de su código de invitación.
3. Si el email ya es de una cuenta de Umbral, NO se vincula solo. El registro público no
   verifica emails: un atacante podría crear antes la cuenta con el email de la víctima y su
   propia contraseña, y quedarse dentro cuando ella entrase con Google (pre-account hijacking).
   Vincular se hace desde Mi cuenta, con la sesión abierta y reautenticándose.
"""

import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import obtener_configuracion
from app.errores import Conflicto, NoAutenticado
from app.modelos import SIN_CONTRASENA, IdentidadExterna, Rol, Usuario
from app.repositorios import RepositorioIdentidades, RepositorioUsuarios
from app.seguridad import reto_pkce
from app.servicios.auditoria import auditar
from app.servicios.empresas import cuenta_habilitada

_TIEMPO_ESPERA = httpx.Timeout(10.0)
_FALLO = "No se ha podido iniciar sesión con el proveedor"


class EmailYaRegistrado(NoAutenticado):
    """El email es de una cuenta que aún no tiene vinculado este proveedor."""


@dataclass(frozen=True)
class Proveedor:
    nombre: str
    url_autorizacion: str
    url_token: str
    alcance: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class PerfilExterno:
    sujeto: str
    email: str | None
    verificado: bool


def proveedores() -> dict[str, Proveedor]:
    """Los que tienen credenciales configuradas. Sin URL pública no hay ninguno."""
    config = obtener_configuracion()
    if not config.url_publica:
        return {}
    todos = [
        Proveedor(
            "google",
            "https://accounts.google.com/o/oauth2/v2/auth",
            "https://oauth2.googleapis.com/token",
            "openid email",
            config.google_client_id,
            config.google_client_secret,
        ),
        Proveedor(
            "github",
            "https://github.com/login/oauth/authorize",
            "https://github.com/login/oauth/access_token",
            "read:user user:email",
            config.github_client_id,
            config.github_client_secret,
        ),
    ]
    return {p.nombre: p for p in todos if p.client_id and p.client_secret}


def url_retorno(proveedor: str) -> str:
    """redirect_uri: tiene que coincidir EXACTAMENTE con la registrada en el proveedor."""
    config = obtener_configuracion()
    return f"{config.url_publica}{config.api_prefijo}/auth/oauth/{proveedor}/callback"


def url_autorizacion(proveedor: Proveedor) -> tuple[str, str, str]:
    """(URL a la que mandar al navegador, state, verificador PKCE)."""
    estado = secrets.token_urlsafe(32)
    verificador = secrets.token_urlsafe(64)  # 86 caracteres: dentro de los 43-128 de la RFC 7636
    parametros = {
        "client_id": proveedor.client_id,
        "redirect_uri": url_retorno(proveedor.nombre),
        "response_type": "code",
        "scope": proveedor.alcance,
        "state": estado,
        "code_challenge": reto_pkce(verificador),
        "code_challenge_method": "S256",
    }
    if proveedor.nombre == "google":
        parametros["prompt"] = "select_account"
    return f"{proveedor.url_autorizacion}?{urlencode(parametros)}", estado, verificador


# --- Lectura de la identidad. Funciones puras: se prueban sin red ---


def perfil_google(datos: dict) -> PerfilExterno:
    return PerfilExterno(
        sujeto=str(datos["sub"]),
        email=datos.get("email"),
        verificado=datos.get("email_verified") is True,
    )


def perfil_github(usuario: dict, emails: list[dict]) -> PerfilExterno:
    # El email público del perfil no está garantizado: se usa el principal, y solo si GitHub
    # lo ha verificado
    principal = next((e for e in emails if e.get("primary") and e.get("verified")), None)
    return PerfilExterno(
        sujeto=str(usuario["id"]),
        email=principal["email"] if principal else None,
        verificado=principal is not None,
    )


async def obtener_perfil(proveedor: Proveedor, codigo: str, verificador: str) -> PerfilExterno:
    """Canjea el código y pide la identidad. Cualquier fallo del proveedor es NoAutenticado."""
    try:
        async with httpx.AsyncClient(timeout=_TIEMPO_ESPERA) as http:
            respuesta = await http.post(
                proveedor.url_token,
                data={
                    "grant_type": "authorization_code",
                    "code": codigo,
                    "redirect_uri": url_retorno(proveedor.nombre),
                    "client_id": proveedor.client_id,
                    "client_secret": proveedor.client_secret,
                    "code_verifier": verificador,
                },
                headers={"Accept": "application/json"},
            )
            respuesta.raise_for_status()
            token = respuesta.json().get("access_token")
            if not token:
                # GitHub responde 200 con {"error": ...} cuando el código no vale
                raise NoAutenticado(_FALLO)
            cabeceras = {"Authorization": f"Bearer {token}"}

            if proveedor.nombre == "google":
                datos = await http.get(
                    "https://openidconnect.googleapis.com/v1/userinfo", headers=cabeceras
                )
                datos.raise_for_status()
                return perfil_google(datos.json())

            cabeceras |= {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            usuario = await http.get("https://api.github.com/user", headers=cabeceras)
            emails = await http.get("https://api.github.com/user/emails", headers=cabeceras)
            usuario.raise_for_status()
            emails.raise_for_status()
            return perfil_github(usuario.json(), emails.json())
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise NoAutenticado(_FALLO) from error


async def resolver_usuario(
    sesion: AsyncSession, proveedor: str, perfil: PerfilExterno, ip: str | None
) -> Usuario:
    """Login: la cuenta de la identidad, o una nueva si el email no existe todavía."""
    usuarios = RepositorioUsuarios(sesion)
    identidad = await RepositorioIdentidades(sesion).por_sujeto(proveedor, perfil.sujeto)
    if identidad:
        usuario = await usuarios.por_id(identidad.usuario_id)
    else:
        email = await _email_verificado(sesion, proveedor, perfil, ip)
        if await usuarios.por_email(email):
            await auditar(
                sesion,
                accion="oauth_email_existente",
                recurso="usuario",
                usuario_id=None,
                ip=ip,
                detalle=proveedor,
            )
            await sesion.commit()
            raise EmailYaRegistrado(_FALLO)
        usuario = await usuarios.crear(email, SIN_CONTRASENA, Rol.usuario, None)
        await _vincular(sesion, usuario, proveedor, perfil, email, "registro_externo", ip)

    if not usuario or not await cuenta_habilitada(sesion, usuario):
        raise NoAutenticado(_FALLO)
    return usuario


async def vincular(
    sesion: AsyncSession, usuario: Usuario, proveedor: str, perfil: PerfilExterno, ip: str | None
) -> None:
    """Desde Mi cuenta: añade el proveedor a la cuenta con la sesión abierta. El email del
    proveedor puede ser distinto del de Umbral: lo que se prueba es que controla las dos."""
    identidad = await RepositorioIdentidades(sesion).por_sujeto(proveedor, perfil.sujeto)
    if identidad:
        if identidad.usuario_id == usuario.id:
            return
        raise Conflicto("Esa cuenta del proveedor ya está vinculada a otro usuario")
    if proveedor in await RepositorioIdentidades(sesion).proveedores_de(usuario.id):
        raise Conflicto("Ya tienes vinculada otra cuenta de ese proveedor")
    email = await _email_verificado(sesion, proveedor, perfil, ip)
    await _vincular(sesion, usuario, proveedor, perfil, email, "vincular_identidad", ip)


async def _email_verificado(
    sesion: AsyncSession, proveedor: str, perfil: PerfilExterno, ip: str | None
) -> str:
    if not perfil.verificado or not perfil.email:
        await auditar(
            sesion,
            accion="oauth_email_no_verificado",
            recurso="usuario",
            usuario_id=None,
            ip=ip,
            detalle=proveedor,
        )
        await sesion.commit()
        raise NoAutenticado(_FALLO)
    return perfil.email.lower()


async def _vincular(
    sesion: AsyncSession,
    usuario: Usuario,
    proveedor: str,
    perfil: PerfilExterno,
    email: str,
    accion: str,
    ip: str | None,
) -> None:
    try:
        await RepositorioIdentidades(sesion).crear(
            IdentidadExterna(
                usuario_id=usuario.id, proveedor=proveedor, sujeto=perfil.sujeto, email=email
            )
        )
    except IntegrityError as error:
        # Dos vueltas simultáneas con la misma identidad: la otra ya la ha vinculado
        await sesion.rollback()
        raise NoAutenticado(_FALLO) from error
    await auditar(
        sesion,
        accion=accion,
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
        detalle=proveedor,
    )
    await sesion.commit()


async def desvincular(
    sesion: AsyncSession, usuario: Usuario, proveedor: str, ip: str | None
) -> None:
    identidades = RepositorioIdentidades(sesion)
    vinculados = await identidades.proveedores_de(usuario.id)
    if proveedor not in vinculados:
        raise Conflicto("Ese proveedor no está vinculado")
    if not usuario.tiene_contrasena and len(vinculados) == 1:
        # Sin contraseña ni otro proveedor, la cuenta se quedaría sin forma de entrar
        raise Conflicto("Es tu única forma de entrar: no se puede desvincular")
    await identidades.borrar(usuario.id, proveedor)
    await auditar(
        sesion,
        accion="desvincular_identidad",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
        detalle=proveedor,
    )
    await sesion.commit()
