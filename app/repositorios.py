"""Acceso a datos. Sin reglas de negocio: los permisos se deciden en los servicios."""

from datetime import datetime

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import (
    Categoria,
    Estado,
    Incidente,
    RegistroAuditoria,
    Rol,
    Severidad,
    TokenRefresco,
    Usuario,
)


class RepositorioUsuarios:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_id(self, usuario_id: int) -> Usuario | None:
        return await self.sesion.get(Usuario, usuario_id)

    async def por_email(self, email: str) -> Usuario | None:
        consulta = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        return await self.sesion.scalar(consulta)

    async def crear(self, email: str, hash_contrasena: str, rol: Rol = Rol.usuario) -> Usuario:
        usuario = Usuario(email=email.lower(), hash_contrasena=hash_contrasena, rol=rol)
        self.sesion.add(usuario)
        await self.sesion.flush()
        return usuario

    async def listar(self, limite: int, desplazamiento: int) -> tuple[int, list[Usuario]]:
        total = await self.sesion.scalar(select(func.count(Usuario.id))) or 0
        consulta = select(Usuario).order_by(Usuario.id).limit(limite).offset(desplazamiento)
        return total, list(await self.sesion.scalars(consulta))


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
        if estado:
            consulta = consulta.where(Incidente.estado == estado)
        if severidad:
            consulta = consulta.where(Incidente.severidad == severidad)
        if categoria:
            consulta = consulta.where(Incidente.categoria == categoria)

        total = await self.sesion.scalar(select(func.count()).select_from(consulta.subquery()))
        pagina = consulta.order_by(Incidente.id.desc()).limit(limite).offset(desplazamiento)
        return total or 0, list(await self.sesion.scalars(pagina))


class RepositorioTokens:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def crear(self, token: TokenRefresco) -> None:
        self.sesion.add(token)
        await self.sesion.flush()

    async def por_hash(self, hash_token: str) -> TokenRefresco | None:
        return await self.sesion.scalar(
            select(TokenRefresco).where(TokenRefresco.hash_token == hash_token)
        )

    async def revocar_familia(self, familia_id: str, momento: datetime) -> None:
        await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.familia_id == familia_id, TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
        )

    async def revocar_de_usuario(self, usuario_id: int, momento: datetime) -> None:
        await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.usuario_id == usuario_id, TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
        )


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
