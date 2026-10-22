"""Cuentas: alta por un admin, registro público, unirse a una empresa y gestión de cuentas.

Quién gestiona a quién:
- admin: a cualquiera menos a sí mismo.
- gestor: solo a los trabajadores (rol usuario) de SU empresa. Para cualquier otra cuenta
  responde 404, como si no existiera: no confirma cuentas de otras empresas.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, Invalido, NoEncontrado
from app.modelos import ROLES_CLIENTE, ROLES_PERSONAL, Rol, Usuario, normalizar_codigo_invitacion
from app.repositorios import RepositorioEmpresas, RepositorioUsuarios
from app.seguridad import hashear_contrasena, verificar_contrasena
from app.servicios.auditoria import auditar
from app.servicios.auth import cerrar_sesiones
from app.servicios.empresas import empresa_asignable
from app.servicios.mfa import quitar as quitar_mfa

_NO_ENCONTRADO = "Usuario no encontrado"
_CODIGO_INVALIDO = "Código de invitación no válido"


async def crear(
    sesion: AsyncSession,
    admin: Usuario,
    email: str,
    contrasena: str,
    rol: Rol,
    empresa_id: int | None,
    ip: str | None,
) -> Usuario:
    if rol in ROLES_PERSONAL and empresa_id is not None:
        raise Invalido("Un admin o analista es personal del MSSP: no puede tener empresa")
    if rol in ROLES_CLIENTE and empresa_id is None:
        # Sin empresa sería una cuenta pendiente: esas solo nacen del registro público
        raise Invalido("Un usuario o gestor pertenece a una empresa cliente: indica cuál")
    if empresa_id is not None:
        await empresa_asignable(sesion, empresa_id)
    usuarios = RepositorioUsuarios(sesion)
    if await usuarios.por_email(email):
        raise Conflicto("El email ya está registrado")
    usuario = await usuarios.crear(email, hashear_contrasena(contrasena), rol, empresa_id)
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


async def registrar(sesion: AsyncSession, email: str, contrasena: str, ip: str | None) -> None:
    """Registro público. La cuenta nace como usuario SIN empresa (pendiente): no ve nada hasta
    unirse a una con el código de invitación que le da su gestor.

    Responde igual exista o no el email, y tardando lo mismo (el hash se calcula siempre): el
    registro no sirve para averiguar qué cuentas existen."""
    hash_contrasena = hashear_contrasena(contrasena)
    usuarios = RepositorioUsuarios(sesion)
    existente = await usuarios.por_email(email)
    if existente is None:
        try:
            usuario = await usuarios.crear(email, hash_contrasena, Rol.usuario, None)
        except IntegrityError:
            # Dos registros simultáneos con el mismo email: el segundo es un duplicado más
            await sesion.rollback()
            existente = await usuarios.por_email(email)
        else:
            await auditar(
                sesion,
                accion="registro",
                recurso="usuario",
                usuario_id=usuario.id,
                recurso_id=usuario.id,
                ip=ip,
            )
            await sesion.commit()
            return

    # Ya existía: no se toca nada, pero queda rastro (un goteo de estos es un sondeo)
    await auditar(
        sesion,
        accion="registro_duplicado",
        recurso="usuario",
        usuario_id=None,
        recurso_id=existente.id if existente else None,
        ip=ip,
    )
    await sesion.commit()


async def nombre_empresa(sesion: AsyncSession, usuario: Usuario) -> str | None:
    """Nombre de la empresa de la cuenta; None para el personal del MSSP y las pendientes."""
    if usuario.empresa_id is None:
        return None
    empresa = await RepositorioEmpresas(sesion).por_id(usuario.empresa_id)
    return empresa.nombre if empresa else None


async def unirse_a_empresa(
    sesion: AsyncSession, usuario: Usuario, codigo: str, ip: str | None
) -> Usuario:
    # Solo un usuario pendiente. Un gestor jamás: si no, cualquier código le haría responsable
    # de una empresa ajena
    if usuario.rol != Rol.usuario or not usuario.pendiente:
        raise Conflicto("Tu cuenta ya pertenece a una empresa")

    empresa = await RepositorioEmpresas(sesion).por_codigo_invitacion(
        normalizar_codigo_invitacion(codigo)
    )
    if not empresa or not empresa.activa:
        # Mismo mensaje para código inventado, viejo (regenerado) o de una empresa de baja
        await auditar(
            sesion,
            accion="union_empresa_fallida",
            recurso="usuario",
            usuario_id=usuario.id,
            recurso_id=usuario.id,
            ip=ip,
        )
        await sesion.commit()
        raise Invalido(_CODIGO_INVALIDO)

    usuario.empresa_id = empresa.id
    await auditar(
        sesion,
        accion="unirse_empresa",
        recurso="empresa",
        usuario_id=usuario.id,
        recurso_id=empresa.id,
        ip=ip,
        detalle=empresa.codigo,
    )
    await sesion.commit()
    return usuario


async def _gestionable(sesion: AsyncSession, actor: Usuario, usuario_id: int) -> Usuario:
    """La cuenta sobre la que `actor` (admin o gestor) quiere actuar, si puede actuar sobre ella."""
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado(_NO_ENCONTRADO)
    if actor.rol == Rol.gestor and (
        usuario.empresa_id != actor.empresa_id or usuario.rol != Rol.usuario
    ):
        # Un gestor solo toca a los trabajadores de su empresa: ni a otro gestor, ni a nadie
        # de fuera. 404 y no 403: no confirma que esa cuenta exista
        if usuario.id != actor.id:
            raise NoEncontrado(_NO_ENCONTRADO)
    return usuario


async def restablecer_contrasena(
    sesion: AsyncSession, actor: Usuario, usuario_id: int, nueva: str, ip: str | None
) -> None:
    usuario = await _gestionable(sesion, actor, usuario_id)
    if usuario.id == actor.id:
        # La propia se cambia en /usuarios/yo/contrasena, que exige la actual
        raise Conflicto("Tu contraseña se cambia desde Mi cuenta")

    usuario.hash_contrasena = hashear_contrasena(nueva)
    # Quien tuviera una sesión abierta con la contraseña vieja la pierde
    await cerrar_sesiones(sesion, usuario)
    await auditar(
        sesion,
        accion="restablecer_contrasena",
        recurso="usuario",
        usuario_id=actor.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()


async def cambiar_rol(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, rol: Rol, ip: str | None
) -> Usuario:
    usuario = await RepositorioUsuarios(sesion).por_id(usuario_id)
    if not usuario:
        raise NoEncontrado(_NO_ENCONTRADO)
    if usuario.id == admin.id:
        # Evita que el último admin se quite el rol por error y deje el sistema sin admin
        raise Conflicto("Un admin no puede cambiar su propio rol")
    if rol in ROLES_PERSONAL and usuario.empresa_id is not None:
        # Un trabajador de un cliente con rol de analista vería los datos de los demás clientes
        raise Conflicto("Un usuario de un cliente no puede ser admin ni analista")
    if rol in ROLES_CLIENTE and usuario.empresa_id is None:
        # Personal del MSSP o cuenta pendiente: sin empresa, no hay cliente que gestionar
        raise Conflicto("Solo una cuenta de una empresa cliente puede ser usuario o gestor")

    anterior = usuario.rol
    usuario.rol = rol
    # Sin cerrar sesiones: el rol no va en el token, usuario_actual lo lee de la BD en cada
    # petición. Ascender o degradar surte efecto en la siguiente petición, con la misma sesión
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
    sesion: AsyncSession, actor: Usuario, usuario_id: int, activo: bool, ip: str | None
) -> Usuario:
    usuario = await _gestionable(sesion, actor, usuario_id)
    if usuario.id == actor.id:
        # Mismo motivo que con el rol: nadie puede dejarse fuera a sí mismo
        raise Conflicto("No puedes desactivar tu propia cuenta")
    if usuario.activo == activo:
        return usuario

    usuario.activo = activo
    if not activo:
        # usuario_actual ya comprueba `activo` en cada petición; cerrar las sesiones evita
        # además que, si se reactiva, vuelvan a valer los tokens de antes de la baja
        await cerrar_sesiones(sesion, usuario)
    await auditar(
        sesion,
        accion="reactivar_usuario" if activo else "desactivar_usuario",
        recurso="usuario",
        usuario_id=actor.id,
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
    # Cierra la sesión en todos los dispositivos AL MOMENTO: quien tuviera un token robado,
    # de acceso o de refresco, lo pierde en su siguiente petición
    await cerrar_sesiones(sesion, usuario)
    await auditar(
        sesion,
        accion="cambio_contrasena",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()


async def restablecer_mfa(
    sesion: AsyncSession, admin: Usuario, usuario_id: int, ip: str | None
) -> Usuario:
    """Para quien ha perdido el móvil y los códigos de recuperación. Comprobar que es quien dice
    ser queda fuera de la app (en persona, por teléfono): por eso solo lo hace un admin."""
    usuario = await _gestionable(sesion, admin, usuario_id)
    if usuario.id == admin.id:
        raise Conflicto("Tu verificación en dos pasos se gestiona desde Mi cuenta")
    if not usuario.mfa_activo:
        raise Conflicto("Esa cuenta no tiene la verificación en dos pasos activa")
    await quitar_mfa(sesion, usuario)
    # Quien tuviera abierta una sesión con el MFA anterior la pierde
    await cerrar_sesiones(sesion, usuario)
    await auditar(
        sesion,
        accion="restablecer_mfa",
        recurso="usuario",
        usuario_id=admin.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
    return usuario
