from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, NoEncontrado
from app.modelos import Rol, Usuario, ahora
from app.repositorios import RepositorioTokens, RepositorioUsuarios
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
