"""Acceso a datos. Sin reglas de negocio: los permisos se deciden en los servicios."""

from datetime import datetime

from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import (
    Categoria,
    CodigoRecuperacion,
    Empresa,
    Estado,
    IdentidadExterna,
    Incidente,
    RegistroAuditoria,
    Rol,
    Severidad,
    TokenRefresco,
    Usuario,
)


class RepositorioEmpresas:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_id(self, empresa_id: int) -> Empresa | None:
        return await self.sesion.get(Empresa, empresa_id)

    async def por_codigo_invitacion(self, codigo: str) -> Empresa | None:
        return await self.sesion.scalar(select(Empresa).where(Empresa.codigo_invitacion == codigo))

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

    async def crear(
        self,
        email: str,
        hash_contrasena: str,
        rol: Rol = Rol.usuario,
        empresa_id: int | None = None,
    ) -> Usuario:
        usuario = Usuario(
            email=email.lower(), hash_contrasena=hash_contrasena, rol=rol, empresa_id=empresa_id
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

    async def marcar_paso_mfa(self, usuario_id: int, paso: int) -> bool:
        """Apunta el paso TOTP como usado si es posterior al último. Atómico, como
        RepositorioTokens.consumir: dos peticiones con el mismo código no pasan las dos."""
        resultado = await self.sesion.execute(
            update(Usuario)
            .where(
                Usuario.id == usuario_id,
                or_(Usuario.mfa_ultimo_paso.is_(None), Usuario.mfa_ultimo_paso < paso),
            )
            .values(mfa_ultimo_paso=paso)
            .execution_options(synchronize_session=False)
        )
        return resultado.rowcount == 1

    async def registrar_fallo_mfa(self, usuario_id: int, maximo: int, hasta: datetime) -> bool:
        """Suma un fallo en la propia BD (no lee-suma-escribe: con peticiones en paralelo se
        perderían fallos) y, al llegar a `maximo`, bloquea hasta `hasta`. True = bloqueada."""
        fallos = await self.sesion.scalar(
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(mfa_fallos=Usuario.mfa_fallos + 1)
            .returning(Usuario.mfa_fallos)
            .execution_options(synchronize_session=False)
        )
        if fallos is None or fallos < maximo:
            return False
        await self.sesion.execute(
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(mfa_fallos=0, mfa_bloqueado_hasta=hasta)
            .execution_options(synchronize_session=False)
        )
        return True

    async def reiniciar_fallos_mfa(self, usuario_id: int) -> None:
        await self.sesion.execute(
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(mfa_fallos=0, mfa_bloqueado_hasta=None)
            .execution_options(synchronize_session=False)
        )

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

    async def consumir(self, token_id: int, momento: datetime) -> bool:
        """Marca el token como usado si nadie lo ha hecho antes. Atómico: con dos peticiones a la
        vez, la base de datos deja que solo una cambie la fila. False = ya estaba usado."""
        resultado = await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.id == token_id, TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
            .execution_options(synchronize_session=False)
        )
        return resultado.rowcount == 1

    async def revocar_familia(self, familia_id: str, momento: datetime) -> None:
        await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.familia_id == familia_id, TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
        )

    async def revocar_de_empresa(self, empresa_id: int, momento: datetime) -> None:
        de_la_empresa = select(Usuario.id).where(Usuario.empresa_id == empresa_id)
        await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.usuario_id.in_(de_la_empresa), TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
        )

    async def revocar_de_usuario(self, usuario_id: int, momento: datetime) -> None:
        await self.sesion.execute(
            update(TokenRefresco)
            .where(TokenRefresco.usuario_id == usuario_id, TokenRefresco.revocado_en.is_(None))
            .values(revocado_en=momento)
        )


class RepositorioCodigosRecuperacion:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def reemplazar(self, usuario_id: int, hashes: list[str]) -> None:
        await self.borrar_de_usuario(usuario_id)
        self.sesion.add_all(
            CodigoRecuperacion(usuario_id=usuario_id, hash_codigo=h) for h in hashes
        )
        await self.sesion.flush()

    async def borrar_de_usuario(self, usuario_id: int) -> None:
        await self.sesion.execute(
            delete(CodigoRecuperacion).where(CodigoRecuperacion.usuario_id == usuario_id)
        )

    async def consumir(self, usuario_id: int, hash_codigo: str, momento: datetime) -> bool:
        """Gasta el código si existe y nadie lo ha usado. Atómico: un solo uso aunque lleguen
        dos peticiones a la vez."""
        resultado = await self.sesion.execute(
            update(CodigoRecuperacion)
            .where(
                CodigoRecuperacion.usuario_id == usuario_id,
                CodigoRecuperacion.hash_codigo == hash_codigo,
                CodigoRecuperacion.usado_en.is_(None),
            )
            .values(usado_en=momento)
            .execution_options(synchronize_session=False)
        )
        return resultado.rowcount == 1

    async def disponibles(self, usuario_id: int) -> int:
        consulta = select(func.count()).where(
            CodigoRecuperacion.usuario_id == usuario_id, CodigoRecuperacion.usado_en.is_(None)
        )
        return await self.sesion.scalar(consulta) or 0


class RepositorioIdentidades:
    def __init__(self, sesion: AsyncSession):
        self.sesion = sesion

    async def por_sujeto(self, proveedor: str, sujeto: str) -> IdentidadExterna | None:
        return await self.sesion.scalar(
            select(IdentidadExterna).where(
                IdentidadExterna.proveedor == proveedor, IdentidadExterna.sujeto == sujeto
            )
        )

    async def crear(self, identidad: IdentidadExterna) -> None:
        self.sesion.add(identidad)
        await self.sesion.flush()

    async def borrar(self, usuario_id: int, proveedor: str) -> None:
        await self.sesion.execute(
            delete(IdentidadExterna).where(
                IdentidadExterna.usuario_id == usuario_id, IdentidadExterna.proveedor == proveedor
            )
        )

    async def proveedores_de(self, usuario_id: int) -> list[str]:
        consulta = (
            select(IdentidadExterna.proveedor)
            .where(IdentidadExterna.usuario_id == usuario_id)
            .order_by(IdentidadExterna.proveedor)
        )
        return list(await self.sesion.scalars(consulta))


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
