"""Clientes del MSSP. Solo los gestiona un admin; nunca se borran, se desactivan."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.errores import Conflicto, Invalido, NoEncontrado
from app.esquemas import EmpresaCrear, EmpresaEditar
from app.modelos import Empresa, Usuario
from app.repositorios import RepositorioEmpresas
from app.servicios.auditoria import auditar


async def cuenta_habilitada(sesion: AsyncSession, usuario: Usuario) -> bool:
    """Un trabajador de un cliente dado de baja pierde el acceso aunque su cuenta siga activa."""
    if not usuario.activo:
        return False
    if usuario.empresa_id is None:
        return True
    empresa = await RepositorioEmpresas(sesion).por_id(usuario.empresa_id)
    return empresa is not None and empresa.activa


async def empresa_asignable(sesion: AsyncSession, empresa_id: int) -> Empresa:
    empresa = await RepositorioEmpresas(sesion).por_id(empresa_id)
    if not empresa or not empresa.activa:
        raise Invalido("La empresa indicada no existe o está desactivada")
    return empresa


async def obtener(sesion: AsyncSession, empresa_id: int) -> Empresa:
    empresa = await RepositorioEmpresas(sesion).por_id(empresa_id)
    if not empresa:
        raise NoEncontrado("Empresa no encontrada")
    return empresa


async def crear(
    sesion: AsyncSession, admin: Usuario, datos: EmpresaCrear, ip: str | None
) -> Empresa:
    repo = RepositorioEmpresas(sesion)
    if await repo.existe(datos.codigo, datos.nombre):
        raise Conflicto("Ya hay una empresa con ese código o ese nombre")
    empresa = await repo.crear(Empresa(**datos.model_dump()))
    await auditar(
        sesion,
        accion="crear_empresa",
        recurso="empresa",
        usuario_id=admin.id,
        recurso_id=empresa.id,
        ip=ip,
        detalle=datos.codigo,
    )
    await sesion.commit()
    return empresa


async def editar(
    sesion: AsyncSession, admin: Usuario, empresa_id: int, datos: EmpresaEditar, ip: str | None
) -> Empresa:
    empresa = await obtener(sesion, empresa_id)
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    if not cambios:
        raise Invalido("No hay campos que modificar")
    if cambios.get("sector") == "":
        cambios["sector"] = None  # cadena vacía = quitar el sector
    if "nombre" in cambios and await RepositorioEmpresas(sesion).existe(
        empresa.codigo, cambios["nombre"], excluir_id=empresa.id
    ):
        raise Conflicto("Ya hay una empresa con ese nombre")

    # Dar de baja corta el acceso al momento: `cuenta_habilitada` mira la empresa en cada petición
    for campo, valor in cambios.items():
        setattr(empresa, campo, valor)
    await auditar(
        sesion,
        accion="editar_empresa",
        recurso="empresa",
        usuario_id=admin.id,
        recurso_id=empresa.id,
        ip=ip,
        detalle=",".join(sorted(cambios)),
    )
    await sesion.commit()
    await sesion.refresh(empresa)
    return empresa
