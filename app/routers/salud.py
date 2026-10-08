from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.dependencias import Sesion

router = APIRouter(tags=["salud"])


@router.get("/salud")
async def salud(sesion: Sesion):
    try:
        await sesion.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse({"estado": "degradado", "bd": "sin conexion"}, status_code=503)
    return {"estado": "ok", "bd": "ok"}
