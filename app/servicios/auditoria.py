from sqlalchemy.ext.asyncio import AsyncSession

from app.modelos import RegistroAuditoria
from app.repositorios import RepositorioAuditoria


async def auditar(
    sesion: AsyncSession,
    *,
    accion: str,
    recurso: str,
    usuario_id: int | None,
    recurso_id: int | None = None,
    ip: str | None = None,
    detalle: str | None = None,
) -> None:
    """Añade el registro a la transacción en curso; el commit lo hace quien llama."""
    await RepositorioAuditoria(sesion).registrar(
        RegistroAuditoria(
            accion=accion,
            recurso=recurso,
            usuario_id=usuario_id,
            recurso_id=recurso_id,
            ip=ip,
            detalle=detalle,
        )
    )
