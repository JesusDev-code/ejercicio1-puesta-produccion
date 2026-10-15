"""Acceso a datos. Sin reglas de negocio: los permisos se deciden en los servicios."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import (
    Categoria,
    Empresa,
    Estado,
    Incidente,
    RegistroAuditoria,
    Rol,
    Severidad,
    Usuario,
)


class RepositorioEmpresas:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_id(self, empresa_id: int) -> Empresa | None:
        return await self.sesion.get(Empresa, empresa_id)

    async def ids_por_codigo(self, codigos: set[str]) -> dict[str, int]:
        if not codigos:
            return {}
        filas = await self.sesion.execute(
            select(Empresa.codigo, Empresa.id).where(Empresa.codigo.in_(codigos))
        )
        return {codigo: empresa_id for codigo, empresa_id in filas.all()}

    async def existe(self, codigo: str, nombre: str, excluir_id: int | None = None) -> bool:
        consulta = select(Empresa.id).where(
            or_(Empresa.codigo == codigo, func.lower(Empresa.nombre) == nombre.lower())
        )
        if excluir_id is not None:
            consulta = consulta.where(Empresa.id != excluir_id)
        return await self.sesion.scalar(consulta.limit(1)) is not None

    async def crear(self, empresa: Empresa) -> Empresa:
        self.sesion.add(empresa)
        await self.sesion.flush()
        return empresa

    async def listar(
        self, activa: bool | None, limite: int, desplazamiento: int
    ) -> tuple[int, list[Empresa]]:
        consulta: Select = select(Empresa)
        if activa is not None:
            consulta = consulta.where(Empresa.activa == activa)
        total = await self.sesion.scalar(select(func.count()).select_from(consulta.subquery()))
        pagina = consulta.order_by(Empresa.nombre).limit(limite).offset(desplazamiento)
        return total or 0, list(await self.sesion.scalars(pagina))


class RepositorioUsuarios:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_id(self, usuario_id: int) -> Usuario | None:
        return await self.sesion.get(Usuario, usuario_id)

    async def por_email(self, email: str) -> Usuario | None:
        consulta = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        return await self.sesion.scalar(consulta)

    async def por_uid(self, firebase_uid: str) -> Usuario | None:
        return await self.sesion.scalar(select(Usuario).where(Usuario.firebase_uid == firebase_uid))

    async def crear(
        self,
        email: str,
        firebase_uid: str | None,
        rol: Rol = Rol.usuario,
        empresa_id: int | None = None,
    ) -> Usuario:
        usuario = Usuario(
            email=email.lower(), firebase_uid=firebase_uid, rol=rol, empresa_id=empresa_id
        )
        self.sesion.add(usuario)
        await self.sesion.flush()
        return usuario

    async def listar(
        self,
        limite: int,
        desplazamiento: int,
        rol: Rol | None = None,
        email: str | None = None,
        empresa_id: int | None = None,
    ) -> tuple[int, list[Usuario]]:
        consulta: Select = select(Usuario)
        if rol:
            consulta = consulta.where(Usuario.rol == rol)
        if empresa_id is not None:
            consulta = consulta.where(Usuario.empresa_id == empresa_id)
        if email:
            # autoescape: un `%` o `_` del cliente se busca literal, no como comodín de LIKE
            consulta = consulta.where(
                func.lower(Usuario.email).contains(email.lower(), autoescape=True)
            )
        total = await self.sesion.scalar(select(func.count()).select_from(consulta.subquery()))
        pagina = consulta.order_by(Usuario.id).limit(limite).offset(desplazamiento)
        return total or 0, list(await self.sesion.scalars(pagina))

    async def emails_por_id(self, ids: set[int]) -> dict[int, str]:
        """Una sola consulta para resolver todos los emails de una respuesta (sin N+1)."""
        if not ids:
            return {}
        filas = await self.sesion.execute(
            select(Usuario.id, Usuario.email).where(Usuario.id.in_(ids))
        )
        return {usuario_id: email for usuario_id, email in filas.all()}


class RepositorioIncidentes:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_id(self, incidente_id: int) -> Incidente | None:
        consulta = select(Incidente).where(
            Incidente.id == incidente_id, Incidente.borrado_en.is_(None)
        )
        return await self.sesion.scalar(consulta)

    async def crear(self, incidente: Incidente) -> Incidente:
        self.sesion.add(incidente)
        await self.sesion.flush()
        await self.sesion.refresh(incidente)
        return incidente

    async def listar(
        self,
        *,
        visible_para: int | None,
        incluir_asignados: bool,
        empresa_id: int | None,
        estado: Estado | None,
        severidad: Severidad | None,
        categoria: Categoria | None,
        limite: int,
        desplazamiento: int,
    ) -> tuple[int, list[Incidente]]:
        """`visible_para=None` devuelve todos (admin). Si no, los que reportó y, con
        `incluir_asignados`, también los que tiene asignados (analista)."""
        consulta: Select = select(Incidente).where(Incidente.borrado_en.is_(None))
        if visible_para is not None:
            condicion = Incidente.reportante_id == visible_para
            if incluir_asignados:
                condicion = or_(condicion, Incidente.analista_id == visible_para)
            consulta = consulta.where(condicion)
        if empresa_id is not None:
            consulta = consulta.where(Incidente.empresa_id == empresa_id)
        if estado:
            consulta = consulta.where(Incidente.estado == estado)
        if severidad:
            consulta = consulta.where(Incidente.severidad == severidad)
        if categoria:
            consulta = consulta.where(Incidente.categoria == categoria)

        total = await self.sesion.scalar(select(func.count()).select_from(consulta.subquery()))
        pagina = consulta.order_by(Incidente.id.desc()).limit(limite).offset(desplazamiento)
        return total or 0, list(await self.sesion.scalars(pagina))


class RepositorioAuditoria:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def registrar(self, registro: RegistroAuditoria) -> None:
        self.sesion.add(registro)
        await self.sesion.flush()

    async def listar(
        self, accion: str | None, limite: int, desplazamiento: int
    ) -> tuple[int, list[RegistroAuditoria]]:
        consulta: Select = select(RegistroAuditoria)
        if accion:
            consulta = consulta.where(RegistroAuditoria.accion == accion)
        total = await self.sesion.scalar(select(func.count()).select_from(consulta.subquery()))
        pagina = consulta.order_by(RegistroAuditoria.id.desc()).limit(limite).offset(desplazamiento)
        return total or 0, list(await self.sesion.scalars(pagina))
