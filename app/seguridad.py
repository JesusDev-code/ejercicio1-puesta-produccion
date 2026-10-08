import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import obtener_configuracion
from app.modelos import ahora

_hasher = PasswordHasher()

# Se verifica contra este hash cuando el email no existe: así un login fallido tarda
# lo mismo exista o no la cuenta (evita la enumeración de usuarios).
_HASH_FICTICIO = _hasher.hash("contrasena-ficticia-para-igualar-tiempos")


def hashear_contrasena(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar_contrasena(hash_guardado: str | None, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado or _HASH_FICTICIO, contrasena) and bool(hash_guardado)
    except (VerificationError, InvalidHashError):
        return False


def crear_token_acceso(usuario_id: int) -> str:
    config = obtener_configuracion()
    momento = ahora()
    datos = {
        "sub": str(usuario_id),
        "tipo": "acceso",
        "iat": momento,
        "exp": momento + timedelta(minutes=config.acceso_minutos),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(datos, config.jwt_secreto, algorithm=config.jwt_algoritmo)


def decodificar_token_acceso(token: str) -> int | None:
    """Devuelve el id de usuario, o None si el token es inválido, ha caducado o no es de acceso."""
    config = obtener_configuracion()
    try:
        datos = jwt.decode(
            token,
            config.jwt_secreto,
            algorithms=[config.jwt_algoritmo],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.PyJWTError:
        return None
    if datos.get("tipo") != "acceso":
        return None
    try:
        return int(datos["sub"])
    except (TypeError, ValueError):
        return None


def generar_token_refresco() -> str:
    return secrets.token_urlsafe(48)


def hashear_token(token: str) -> str:
    # Token aleatorio de alta entropía: basta un hash rápido (la fuerza bruta no es viable)
    return hashlib.sha256(token.encode()).hexdigest()
