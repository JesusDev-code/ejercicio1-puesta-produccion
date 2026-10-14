from typing import Annotated

from fastapi import APIRouter, Query, status

from app.dependencias import Admin, IpCliente, Sesion
from app.esquemas import EmpresaCrear, EmpresaEditar, EmpresaSalida, Pagina
from app.repositorios import RepositorioEmpresas
from app.servicios import empresas as servicio

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("", response_model=Pagina[EmpresaSalida])
async def listar(
    _: Admin,
    sesion: Sesion,
    activa: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
):
    total, elementos = await RepositorioEmpresas(sesion).listar(activa, limite, desplazamiento)
    return Pagina(total=total, limite=limite, desplazamiento=desplazamiento, elementos=elementos)


@router.post("", response_model=EmpresaSalida, status_code=status.HTTP_201_CREATED)
async def crear(datos: EmpresaCrear, admin: Admin, sesion: Sesion, ip: IpCliente):
    return await servicio.crear(sesion, admin, datos, ip)


@router.get("/{empresa_id}", response_model=EmpresaSalida)
async def obtener(empresa_id: int, _: Admin, sesion: Sesion):
    return await servicio.obtener(sesion, empresa_id)


@router.patch("/{empresa_id}", response_model=EmpresaSalida)
async def editar(
    empresa_id: int, datos: EmpresaEditar, admin: Admin, sesion: Sesion, ip: IpCliente
):
    return await servicio.editar(sesion, admin, empresa_id, datos, ip)
