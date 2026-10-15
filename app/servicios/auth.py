import secrets
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import obtener_configuracion
from app.errores import NoAutenticado
from app.esquemas import ParTokens
from app.modelos import TokenRefresco, Usuario, a_utc, ahora
from app.repositorios import RepositorioTokens, RepositorioUsuarios
from app.seguridad import (
    crear_token_acceso,
    generar_token_refresco,
    hashear_token,
    verificar_contrasena,
)
from app.servicios.auditoria import auditar
from app.servicios.empresas import cuenta_habilitada

_CREDENCIALES_INVALIDAS = "Credenciales inválidas"
# Mensaje de error, no un secreto: bandit lo confunde por la palabra "token"
_TOKEN_INVALIDO = "Token de refresco inválido"  # noqa: S105  # nosec B105


async def _emitir_tokens(sesion: AsyncSession, usuario: Usuario, familia_id: str) -> ParTokens:
    config = obtener_configuracion()
    token_refresco = generar_token_refresco()
    await RepositorioTokens(sesion).crear(
        TokenRefresco(
            usuario_id=usuario.id,
            hash_token=hashear_token(token_refresco),
            familia_id=familia_id,
            expira_en=ahora() + timedelta(days=config.refresco_dias),
        )
    )
    return ParTokens(
        token_acceso=crear_token_acceso(usuario.id, usuario.version_sesion),
        token_refresco=token_refresco,
        expira_en_segundos=config.acceso_minutos * 60,
    )


async def cerrar_sesiones(sesion: AsyncSession, usuario: Usuario) -> None:
    """Cierra la sesión del usuario en todos sus dispositivos, AL MOMENTO.

    Revocar los refresh tokens impide renovar; subir la versión de sesión invalida además los
    access tokens ya emitidos, que si no seguirían valiendo hasta caducar (15 min)."""
    await RepositorioTokens(sesion).revocar_de_usuario(usuario.id, ahora())
    usuario.version_sesion += 1


async def login(sesion: AsyncSession, email: str, contrasena: str, ip: str | None) -> ParTokens:
    usuario = await RepositorioUsuarios(sesion).por_email(email)
    hash_guardado = usuario.hash_contrasena if usuario else None

    # Se verifica la contraseña siempre, exista o no el usuario: mismo tiempo de respuesta
    contrasena_ok = verificar_contrasena(hash_guardado, contrasena)
    if not contrasena_ok or not usuario or not await cuenta_habilitada(sesion, usuario):
        await auditar(
            sesion,
            accion="login_fallido",
            recurso="usuario",
            usuario_id=usuario.id if usuario else None,
            ip=ip,
            detalle=None if usuario else "email inexistente",
        )
        await sesion.commit()
        raise NoAutenticado(_CREDENCIALES_INVALIDAS)

    tokens = await _emitir_tokens(sesion, usuario, familia_id=secrets.token_hex(16))
    await auditar(sesion, accion="login", recurso="usuario", usuario_id=usuario.id, ip=ip)
    await sesion.commit()
    return tokens


async def _reutilizacion(
    sesion: AsyncSession, guardado: TokenRefresco, momento: datetime, ip: str | None
) -> NoReturn:
    """Un token ya rotado se ha vuelto a usar: alguien tiene una copia (no se sabe si es el
    legítimo o el atacante). Se revoca toda la familia y los dos tienen que volver a entrar."""
    await RepositorioTokens(sesion).revocar_familia(guardado.familia_id, momento)
    # El access token que el atacante obtuvo con su copia caería solo en 15 min: así, ya.
    # Los otros dispositivos del usuario conservan su refresh y se recuperan sin notarlo
    usuario = await RepositorioUsuarios(sesion).por_id(guardado.usuario_id)
    if usuario:
        usuario.version_sesion += 1
    await auditar(
        sesion,
        accion="reutilizacion_token",
        recurso="token_refresco",
        usuario_id=guardado.usuario_id,
        recurso_id=guardado.id,
        ip=ip,
        detalle="familia revocada",
    )
    await sesion.commit()
    raise NoAutenticado(_TOKEN_INVALIDO)


async def refrescar(sesion: AsyncSession, token: str, ip: str | None) -> ParTokens:
    repo = RepositorioTokens(sesion)
    guardado = await repo.por_hash(hashear_token(token))
    if not guardado:
        raise NoAutenticado(_TOKEN_INVALIDO)

    momento = ahora()
    if guardado.revocado_en is not None:
        await _reutilizacion(sesion, guardado, momento, ip)

    if a_utc(guardado.expira_en) <= momento:
        raise NoAutenticado(_TOKEN_INVALIDO)

    usuario = await RepositorioUsuarios(sesion).por_id(guardado.usuario_id)
    if not usuario or not await cuenta_habilitada(sesion, usuario):
        raise NoAutenticado(_TOKEN_INVALIDO)

    # La lectura de arriba no basta: dos peticiones simultáneas con el mismo token la pasarían
    # las dos. El UPDATE condicional es la comprobación de verdad y solo lo gana una
    if not await repo.consumir(guardado.id, momento):
        await _reutilizacion(sesion, guardado, momento, ip)
    tokens = await _emitir_tokens(sesion, usuario, familia_id=guardado.familia_id)
    await sesion.commit()
    return tokens


async def logout(sesion: AsyncSession, token: str, ip: str | None) -> None:
    repo = RepositorioTokens(sesion)
    guardado = await repo.por_hash(hashear_token(token))
    # Respuesta idéntica exista o no el token: no se filtra información
    if guardado:
        await repo.revocar_familia(guardado.familia_id, ahora())
        await auditar(
            sesion, accion="logout", recurso="usuario", usuario_id=guardado.usuario_id, ip=ip
        )
        await sesion.commit()
