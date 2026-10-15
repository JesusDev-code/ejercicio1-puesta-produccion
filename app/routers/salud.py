from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import obtener_configuracion
from app.dependencias import Sesion
from app.esquemas import ConfigCliente, ConfigFirebase

router = APIRouter(tags=["salud"])


@router.get("/salud")
async def salud(sesion: Sesion):
    try:
        await sesion.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"estado": "degradado", "bd": "sin conexion"}, status_code=503)
    return {"estado": "ok", "bd": "ok"}


@router.get("/config/cliente", response_model=ConfigCliente)
async def config_cliente():
    """Lo que el front necesita para arrancar el SDK de Firebase. Solo valores públicos: la
    credencial de la cuenta de servicio nunca sale de la API."""
    config = obtener_configuracion()
    return ConfigCliente(
        firebase=ConfigFirebase(
            apiKey=config.firebase_api_key,
            authDomain=config.firebase_auth_domain,
            projectId=config.firebase_project_id,
            emulador=config.firebase_auth_emulator_host or None,
        )
    )
