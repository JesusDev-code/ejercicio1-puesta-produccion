"""Gestión de cuentas. Las contraseñas viven en Firebase; aquí se decide quién puede tocarlas
y queda la auditoría. El rol, la empresa y `activo` son nuestros y se leen en cada petición."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, Invalido, NoEncontrado
from app.identidad import EmailYaRegistrado, identidad
from app.modelos import Rol, Usuario
from app.repositorios import RepositorioUsuarios
from app.servicios.auditoria import auditar
from app.servicios.empresas import empresa_asignable

# Roles del MSSP: ven datos de todos los clientes, así que nunca pertenecen a uno
ROLES_PERSONAL = {Rol.admin, Rol.analista}


async def crear(
    sesion: AsyncSession,
    admin: Usuario,
    email: str,
    contrasena: str,
    rol: Rol,
    empresa_id: int | None,
    ip: str | None,
) -> Usuario:
    if empresa_id is not None:
        if rol in ROLES_PERSONAL:
            raise Invalido("Un admin o analista es personal del MSSP: no puede tener empresa")
        await empresa_asignable(sesion, empresa_id)
    usuarios = RepositorioUsuarios(sesion)
    if await usuarios.por_email(email):
        raise Conflicto("El email ya está registrado")
    try:
        uid = await identidad().crear(email, contrasena)
    except EmailYaRegistrado as e:
        # Existe en Firebase pero no aquí (creada a mano en la consola): no se adopta en silencio
        raise Conflicto("El email ya existe en el proveedor de identidad") from e
    # Si el insert fallara, la cuenta de Firebase queda huérfana: sin fila aquí no entra a nada
    usuario = await usuarios.crear(email, uid, rol, empresa_id)
    await auditar(
        sesion,
        accion="crear_usuario",
        recurso="usuario",
        usuario_id=admin.id,
        recurso_id=usuario.id,
        ip=ip,
        detalle=f"{email} ({rol}, empresa {empresa_id})" if empresa_id else f"{email} ({rol})",
    )
    await sesion.commit()
    return usuario


async def restablecer_contrasena(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, nueva: str, ip: str | None
) -> None:
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    if usuario.id == admin.id:
        # La propia se cambia en /usuarios/yo/contrasena, que exige la actual
        raise Conflicto("Tu contraseña se cambia desde Mi cuenta")

    if usuario.firebase_uid is None:
        # Cuenta anterior a Firebase: restablecerla es lo que la migra
        try:
            usuario.firebase_uid = await identidad().crear(usuario.email, nueva)
        except EmailYaRegistrado as e:
            raise Conflicto("El email ya existe en el proveedor de identidad") from e
    else:
        await identidad().cambiar_contrasena(usuario.firebase_uid, nueva)
        # Quien tuviera una sesión abierta con la contraseña vieja la pierde
        await identidad().revocar(usuario.firebase_uid)
    await auditar(
        sesion,
        accion="restablecer_contrasena",
        recurso="usuario",
        usuario_id=admin.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()


async def cambiar_rol(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, rol: Rol, ip: str | None
) -> Usuario:
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado("Usuario no encontrado")
    if usuario.id == admin.id:
        # Evita que el último admin se quite el rol por error y deje el sistema sin admin
        raise Conflicto("Un admin no puede cambiar su propio rol")
    if rol in ROLES_PERSONAL and usuario.empresa_id is not None:
        # Un trabajador de un cliente con rol de analista vería los datos de los demás clientes
        raise Conflicto("Un usuario de un cliente no puede ser admin ni analista")

    anterior = usuario.rol
    usuario.rol = rol
    # El rol se lee de la BD en cada petición: el cambio es inmediato sin revocar nada
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
    if usuario.firebase_uid:
        # Nuestra BD ya corta el acceso en la siguiente petición; deshabilitarla en Firebase
        # impide además que pueda iniciar sesión y obtener tokens nuevos
        await identidad().activar(usuario.firebase_uid, activo)
        if not activo:
            await identidad().revocar(usuario.firebase_uid)
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
    if usuario.firebase_uid is None:
        raise Conflicto(
            "Tu cuenta aún no está migrada: pide a un admin que restablezca la contraseña"
        )
    # Se exige la contraseña actual: un ID token robado no basta para secuestrar la cuenta
    if not await identidad().comprobar_contrasena(usuario.email, actual):
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

    await identidad().cambiar_contrasena(usuario.firebase_uid, nueva)
    # Cierra la sesión en todos los dispositivos; el front vuelve a entrar con la nueva
    await identidad().revocar(usuario.firebase_uid)
    await auditar(
        sesion,
        accion="cambio_contrasena",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
