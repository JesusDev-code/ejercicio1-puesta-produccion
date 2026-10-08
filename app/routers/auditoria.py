from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencias import Admin, Sesion
from app.esquemas import AuditoriaSalida, Pagina
from app.repositorios import RepositorioAuditoria

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=Pagina[AuditoriaSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    accion: Annotated[str | None, Query(max_length=50)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioAuditoria(sesion).listar(accion, limite, desplazamiento)
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)
