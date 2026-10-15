"""Reglas de negocio de los incidentes. Todos los permisos se deciden aquí, en un solo sitio.

Política de respuestas:
- Si el usuario no puede VER el incidente → 404 (no se confirma que exista).
- Si lo ve pero no puede hacer esa acción → 403.
- Si puede, pero el estado actual no lo permite → 409.

Aislamiento entre clientes: un usuario de una empresa nunca ve nada de otra, aunque una
regla de rol lo permitiera. Se comprueba primero y por separado (defensa en profundidad).

Quién ve qué:
- admin: todo.
- analista: lo que reportó y lo que tiene asignado.
- gestor: todo lo de SU empresa (es el responsable del cliente).
- usuario: solo lo que él reportó.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, Invalido, NoEncontrado, Prohibido
from app.esquemas import IncidenteCrear, IncidenteEditar
from app.modelos import Categoria, Estado, Incidente, Rol, Severidad, Usuario, ahora
from app.repositorios import RepositorioIncidentes, RepositorioUsuarios
from app.servicios.auditoria import auditar

TRANSICIONES: dict[Estado, set[Estado]] = {
    Estado.abierto: {Estado.en_analisis},
    Estado.en_analisis: {Estado.resuelto},
    Estado.resuelto: {Estado.cerrado},
    Estado.cerrado: {Estado.abierto},  # reapertura: solo admin
}


async def emails_de(sesion: AsyncSession, incidentes: list[Incidente]) -> dict[int, str]:
    """Emails de reportantes y analistas de los incidentes que ya se van a devolver.
    Solo se resuelven los de incidentes visibles: no abre ninguna vía nueva de enumeración."""
    ids = {i.reportante_id for i in incidentes} | {
        i.analista_id for i in incidentes if i.analista_id
    }
    return await RepositorioUsuarios(sesion).emails_por_id(ids)


def es_analista_asignado(usuario: Usuario, incidente: Incidente) -> bool:
    return usuario.rol == Rol.analista and incidente.analista_id == usuario.id


def misma_empresa(usuario: Usuario, incidente: Incidente) -> bool:
    """El personal del MSSP cruza clientes; nadie más. Se decide por el ROL: una cuenta de
    cliente sin empresa (pendiente) no es personal y no ve nada de nadie."""
    if usuario.es_personal:
        return True
    return usuario.empresa_id is not None and usuario.empresa_id == incidente.empresa_id


def puede_ver(usuario: Usuario, incidente: Incidente) -> bool:
    if not misma_empresa(usuario, incidente):
        return False
    return (
        usuario.rol in (Rol.admin, Rol.gestor)
        or incidente.reportante_id == usuario.id
        or es_analista_asignado(usuario, incidente)
    )


def puede_ver_internas(usuario: Usuario, incidente: Incidente) -> bool:
    return usuario.rol == Rol.admin or es_analista_asignado(usuario, incidente)


async def _obtener_visible(sesion: AsyncSession, usuario: Usuario, incidente_id: int) -> Incidente:
    incidente = await RepositorioIncidentes(sesion).por_id(incidente_id)
    if not incidente or not puede_ver(usuario, incidente):
        raise NoEncontrado("Incidente no encontrado")
    return incidente


async def crear(
    sesion: AsyncSession, usuario: Usuario, datos: IncidenteCrear, ip: str | None
) -> Incidente:
    incidente = await RepositorioIncidentes(sesion).crear(
        Incidente(
            **datos.model_dump(),
            reportante_id=usuario.id,
            empresa_id=usuario.empresa_id,
            estado=Estado.abierto,
        )
    )
    await auditar(
        sesion,
        accion="crear_incidente",
        recurso="incidente",
        usuario_id=usuario.id,
        recurso_id=incidente.id,
        ip=ip,
    )
    await sesion.commit()
    return incidente


async def listar(
    sesion: AsyncSession,
    usuario: Usuario,
    *,
    empresa_id: int | None = None,
    estado: Estado | None,
    severidad: Severidad | None,
    categoria: Categoria | None,
    limite: int,
    desplazamiento: int,
) -> tuple[int, list[Incidente]]:
    # Quien no es personal del MSSP no elige empresa: se le fija la suya, mande lo que mande
    if not usuario.es_personal:
        if usuario.empresa_id is None:
            # Cuenta de cliente sin empresa: sin filtro de empresa, un gestor vería TODO.
            # La dependencia ya lo impide; esto es la segunda barrera, por si un día falla
            return 0, []
        empresa_id = usuario.empresa_id
    return await RepositorioIncidentes(sesion).listar(
        visible_para=None if usuario.rol in (Rol.admin, Rol.gestor) else usuario.id,
        incluir_asignados=usuario.rol == Rol.analista,
        empresa_id=empresa_id,
        estado=estado,
        severidad=severidad,
        categoria=categoria,
        limite=limite,
        desplazamiento=desplazamiento,
    )


async def obtener(sesion: AsyncSession, usuario: Usuario, incidente_id: int) -> Incidente:
    return await _obtener_visible(sesion, usuario, incidente_id)


async def editar(
    sesion: AsyncSession,
    usuario: Usuario,
    incidente_id: int,
    datos: IncidenteEditar,
    ip: str | None,
) -> Incidente:
    incidente = await _obtener_visible(sesion, usuario, incidente_id)
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    if not cambios:
        raise Invalido("No hay campos que modificar")

    if usuario.rol != Rol.admin:
        if incidente.reportante_id != usuario.id:
            raise Prohibido("Solo el reportante o un admin pueden editar el incidente")
        if incidente.estado != Estado.abierto:
            # Una vez en análisis, el reporte original queda congelado como evidencia
            raise Conflicto("Solo se puede editar un incidente en estado 'abierto'")

    for campo, valor in cambios.items():
        setattr(incidente, campo, valor)
    await auditar(
        sesion,
        accion="editar_incidente",
        recurso="incidente",
        usuario_id=usuario.id,
        recurso_id=incidente.id,
        ip=ip,
        detalle=",".join(sorted(cambios)),
    )
    await sesion.commit()
    await sesion.refresh(incidente)
    return incidente


async def cambiar_estado(
    sesion: AsyncSession, usuario: Usuario, incidente_id: int, nuevo: Estado, ip: str | None
) -> Incidente:
    incidente = await _obtener_visible(sesion, usuario, incidente_id)
    es_admin = usuario.rol == Rol.admin
    if not (es_admin or es_analista_asignado(usuario, incidente)):
        raise Prohibido("Solo el analista asignado o un admin pueden cambiar el estado")

    actual = incidente.estado
    if nuevo not in TRANSICIONES[actual]:
        raise Conflicto(f"Transición no permitida: {actual} -> {nuevo}")
    if actual == Estado.cerrado and not es_admin:
        raise Prohibido("Solo un admin puede reabrir un incidente")
    if nuevo == Estado.en_analisis and incidente.analista_id is None:
        raise Conflicto("Hay que asignar un analista antes de pasar a 'en_analisis'")

    incidente.estado = nuevo
    await auditar(
        sesion,
        accion="cambio_estado",
        recurso="incidente",
        usuario_id=usuario.id,
        recurso_id=incidente.id,
        ip=ip,
        detalle=f"{actual} -> {nuevo}",
    )
    await sesion.commit()
    await sesion.refresh(incidente)
    return incidente


async def asignar(
    sesion: AsyncSession, admin: Usuario, incidente_id: int, analista_id: int, ip: str | None
) -> Incidente:
    incidente = await _obtener_visible(sesion, admin, incidente_id)
    if incidente.estado == Estado.cerrado:
        raise Conflicto("No se puede asignar un incidente cerrado")

    analista = await RepositorioUsuarios(sesion).por_id(analista_id)
    if (
        not analista
        or not analista.activo
        or analista.rol != Rol.analista
        or analista.empresa_id is not None
    ):
        raise Invalido("El usuario indicado no es un analista activo")

    anterior = incidente.analista_id
    incidente.analista_id = analista.id
    await auditar(
        sesion,
        accion="asignar_incidente",
        recurso="incidente",
        usuario_id=admin.id,
        recurso_id=incidente.id,
        ip=ip,
        detalle=f"{anterior} -> {analista.id}",
    )
    await sesion.commit()
    await sesion.refresh(incidente)
    return incidente


async def actualizar_notas(
    sesion: AsyncSession, usuario: Usuario, incidente_id: int, notas: str, ip: str | None
) -> Incidente:
    incidente = await _obtener_visible(sesion, usuario, incidente_id)
    if not puede_ver_internas(usuario, incidente):
        raise Prohibido("Solo el analista asignado o un admin pueden escribir notas internas")

    incidente.notas_internas = notas
    await auditar(
        sesion,
        accion="editar_notas",
        recurso="incidente",
        usuario_id=usuario.id,
        recurso_id=incidente.id,
        ip=ip,
    )
    await sesion.commit()
    await sesion.refresh(incidente)
    return incidente


async def borrar(sesion: AsyncSession, admin: Usuario, incidente_id: int, ip: str | None) -> None:
    incidente = await _obtener_visible(sesion, admin, incidente_id)
    # Borrado lógico: el registro se conserva como evidencia
    incidente.borrado_en = ahora()
    await auditar(
        sesion,
        accion="borrar_incidente",
        recurso="incidente",
        usuario_id=admin.id,
        recurso_id=incidente.id,
        ip=ip,
    )
    await sesion.commit()
