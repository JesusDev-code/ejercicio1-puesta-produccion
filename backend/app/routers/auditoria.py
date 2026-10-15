from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencias import Admin, Sesion
from app.esquemas import AuditoriaSalida, Pagina
from app.repositorios import RepositorioAuditoria, RepositorioUsuarios

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=Pagina[AuditoriaSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    accion: Annotated[str | None, Query(max_length=50)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, registros = await RepositorioAuditoria(sesion).listar(accion, limite, desplazamiento)
    emails = await RepositorioUsuarios(sesion).emails_por_id(
        {r.usuario_id for r in registros if r.usuario_id}
    )
    elementos = []
    for registro in registros:
        salida = AuditoriaSalida.model_validate(registro)
        salida.usuario_email = emails.get(registro.usuario_id) if registro.usuario_id else None
        elementos.append(salida)
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)
