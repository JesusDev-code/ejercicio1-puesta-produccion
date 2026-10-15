from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import obtener_configuracion

# Almacenamiento en memoria: válido con un único proceso de uvicorn.
# Con varios workers o réplicas habría que pasar a Redis (storage_uri).
limitador = Limiter(
    key_func=get_remote_address,
    enabled=obtener_configuracion().limitador_activo,
)
