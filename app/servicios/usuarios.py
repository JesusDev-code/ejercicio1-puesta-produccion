from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, Invalido, NoEncontrado
from app.modelos import Rol, Usuario, ahora
from app.repositorios import RepositorioTokens, RepositorioUsuarios
from app.seguridad import hashear_contrasena, verificar_contrasena
from app.servicios.auditoria import auditar


async def cambiar_rol(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, rol: Rol, ip: str | None
) -> Usuario:
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    if usuario.id == admin.id:
        # Evita que el último admin se quite el rol por error y deje el sistema sin admin
        raise Conflicto("Un admin no puede cambiar su propio rol")

    anterior = usuario.rol
    usuario.rol = rol
    # Cambiar privilegios invalida las sesiones abiertas: se obliga a volver a entrar
    await RepositorioTokens(sesion).revocar_de_usuario(usuario.id, ahora())
    await auditar(
        sesion,
        accion="cambio_rol",
        recurso="usuario",
        usuario_id=admin.id,
        recurso_id=usuario.id,
        ip=ip,
        detalle=f"{anterior} -> {rol}",
    )
    await sesion.commit()
    return usuario


async def cambiar_activo(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, activo: bool, ip: str | None
) -> Usuario:
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    if usuario.id == admin.id:
        # Mismo motivo que con el rol: un admin no puede dejarse fuera a sí mismo
        raise Conflicto("Un admin no puede desactivar su propia cuenta")
    if usuario.activo == activo:
        return usuario

    usuario.activo = activo
    if not activo:
        # El access token ya deja de valer (usuario_actual comprueba `activo` en cada
        # petición); revocar los refresh evita que se pueda renovar la sesión
        await RepositorioTokens(sesion).revocar_de_usuario(usuario.id, ahora())
    await auditar(
        sesion,
        accion="reactivar_usuario" if activo else "desactivar_usuario",
        recurso="usuario",
        usuario_id=admin.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
    return usuario


async def cambiar_contrasena(
    sesion: AsyncSession, usuario: Usuario, actual: str, nueva: str, ip: str | None
) -> None:
    # Se exige la contraseña actual: un access token robado no basta para secuestrar la cuenta
    if not verificar_contrasena(usuario.hash_contrasena, actual):
        await auditar(
            sesion,
            accion="cambio_contrasena_fallido",
            recurso="usuario",
            usuario_id=usuario.id,
            recurso_id=usuario.id,
            ip=ip,
        )
        await sesion.commit()
        raise Invalido("La contraseña actual no es correcta")
    if actual == nueva:
        raise Invalido("La nueva contraseña debe ser distinta de la actual")

    usuario.hash_contrasena = hashear_contrasena(nueva)
    # Cierra la sesión en todos los dispositivos: si alguien tenía un refresh, lo pierde
    await RepositorioTokens(sesion).revocar_de_usuario(usuario.id, ahora())
    await auditar(
        sesion,
        accion="cambio_contrasena",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
