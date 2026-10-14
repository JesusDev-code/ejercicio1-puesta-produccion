import secrets
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import obtener_configuracion
from app.errores import NoAutenticado
from app.esquemas import ParTokens
from app.modelos import TokenRefresco, a_utc, ahora
from app.repositorios import RepositorioTokens, RepositorioUsuarios
from app.seguridad import (
    crear_token_acceso,
    generar_token_refresco,
    hashear_token,
    verificar_contrasena,
)
from app.servicios.auditoria import auditar

_CREDENCIALES_INVALIDAS = "Credenciales inválidas"
# Mensaje de error, no un secreto: bandit lo confunde por la palabra "token"
_TOKEN_INVALIDO = "Token de refresco inválido"  # noqa: S105  # nosec B105


async def _emitir_tokens(sesion: AsyncSession, usuario_id: int, familia_id: str) -> ParTokens:
    config = obtener_configuracion()
    token_refresco = generar_token_refresco()
    await RepositorioTokens(sesion).crear(
        TokenRefresco(
            usuario_id=usuario_id,
            hash_token=hashear_token(token_refresco),
            familia_id=familia_id,
            expira_en=ahora() + timedelta(days=config.refresco_dias),
        )
    )
    return ParTokens(
        token_acceso=crear_token_acceso(usuario_id),
        token_refresco=token_refresco,
        expira_en_segundos=config.acceso_minutos * 60,
    )


async def login(sesion: AsyncSession, email: str, contrasena: str, ip: str | None) -> ParTokens:
    usuario = await RepositorioUsuarios(sesion).por_email(email)
    hash_guardado = usuario.hash_contrasena if usuario else None

    if not verificar_contrasena(hash_guardado, contrasena) or not usuario or not usuario.activo:
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

    tokens = await _emitir_tokens(sesion, usuario.id, familia_id=secrets.token_hex(16))
    await auditar(sesion, accion="login", recurso="usuario", usuario_id=usuario.id, ip=ip)
    await sesion.commit()
    return tokens


async def refrescar(sesion: AsyncSession, token: str, ip: str | None) -> ParTokens:
    repo = RepositorioTokens(sesion)
    guardado = await repo.por_hash(hashear_token(token))
    if not guardado:
        raise NoAutenticado(_TOKEN_INVALIDO)

    momento = ahora()
    if guardado.revocado_en is not None:
        # Un token ya rotado se ha vuelto a usar: alguien tiene una copia.
        # Se revoca toda la familia y ambos (legítimo y atacante) tienen que volver a entrar.
        await repo.revocar_familia(guardado.familia_id, momento)
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

    if a_utc(guardado.expira_en) <= momento:
        raise NoAutenticado(_TOKEN_INVALIDO)

    usuario = await RepositorioUsuarios(sesion).por_id(guardado.usuario_id)
    if not usuario or not usuario.activo:
        raise NoAutenticado(_TOKEN_INVALIDO)

    guardado.revocado_en = momento
    tokens = await _emitir_tokens(sesion, usuario.id, familia_id=guardado.familia_id)
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
