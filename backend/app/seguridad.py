import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import obtener_configuracion
from app.modelos import a_utc, ahora

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


@dataclass(frozen=True)
class DatosAcceso:
    usuario_id: int
    version_sesion: int
    # Hora del login original (no del último refresco). None en tokens de antes de existir
    autenticado_en: datetime | None


def crear_token_acceso(
    usuario_id: int, version_sesion: int, autenticado_en: datetime | None = None
) -> str:
    config = obtener_configuracion()
    momento = ahora()
    datos = {
        "sub": str(usuario_id),
        "tipo": "acceso",
        "ver": version_sesion,
        "iat": momento,
        "exp": momento + timedelta(minutes=config.acceso_minutos),
        "jti": secrets.token_hex(8),
    }
    if autenticado_en is not None:
        # a_utc: SQLite la devuelve sin zona, y .timestamp() la tomaría como hora local
        datos["aut"] = int(a_utc(autenticado_en).timestamp())
    return jwt.encode(datos, config.jwt_secreto, algorithm=config.jwt_algoritmo)


def decodificar_token_acceso(token: str) -> DatosAcceso | None:
    """None si el token es inválido, ha caducado o no es de acceso. Si la versión sigue vigente
    lo decide quien tiene el usuario (la BD)."""
    config = obtener_configuracion()
    try:
        datos = jwt.decode(
            token,
            config.jwt_secreto,
            algorithms=[config.jwt_algoritmo],
            options={"require": ["exp", "sub", "iat", "ver"]},
        )
    except jwt.PyJWTError:
        return None
    if datos.get("tipo") != "acceso":
        return None
    try:
        aut = datos.get("aut")
        return DatosAcceso(
            int(datos["sub"]),
            int(datos["ver"]),
            datetime.fromtimestamp(int(aut), UTC) if aut is not None else None,
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def generar_token_refresco() -> str:
    return secrets.token_urlsafe(48)


def hashear_token(token: str) -> str:
    # Token aleatorio de alta entropía: basta un hash rápido (la fuerza bruta no es viable)
    return hashlib.sha256(token.encode()).hexdigest()


# --- Tokens de un paso intermedio (desafío MFA, estado OAuth) ---
#
# Se firman con el mismo secreto que el access token, pero cada uno lleva su `tipo` y
# decodificar_token_acceso exige "acceso": ninguno de los dos sirve como Bearer.


def _firmar(datos: dict, minutos: int) -> str:
    config = obtener_configuracion()
    momento = ahora()
    datos = {**datos, "iat": momento, "exp": momento + timedelta(minutes=minutos)}
    return jwt.encode(datos, config.jwt_secreto, algorithm=config.jwt_algoritmo)


def _verificar(token: str, tipo: str, obligatorios: list[str]) -> dict | None:
    config = obtener_configuracion()
    try:
        datos = jwt.decode(
            token,
            config.jwt_secreto,
            algorithms=[config.jwt_algoritmo],
            options={"require": ["exp", "iat", *obligatorios]},
        )
    except jwt.PyJWTError:
        return None
    return datos if datos.get("tipo") == tipo else None


DESAFIO_MFA_MINUTOS = 5


def crear_desafio_mfa(usuario_id: int, version_sesion: int) -> str:
    """Prueba de que la contraseña (o Google/GitHub) ya se ha superado. Solo vale para
    /auth/mfa, junto con un código, y caduca en 5 minutos."""
    return _firmar(
        {"sub": str(usuario_id), "tipo": "mfa", "ver": version_sesion}, DESAFIO_MFA_MINUTOS
    )


def decodificar_desafio_mfa(token: str) -> tuple[int, int] | None:
    datos = _verificar(token, "mfa", ["sub", "ver"])
    if datos is None:
        return None
    try:
        return int(datos["sub"]), int(datos["ver"])
    except (TypeError, ValueError):
        return None


def crear_estado_oauth(
    proveedor: str, estado: str, verificador: str, vincular_a: tuple[int, int] | None = None
) -> str:
    """Lo que el navegador guarda entre la ida al proveedor y la vuelta: el `state` (CSRF del
    login) y el verificador PKCE. Firmado: el cliente no puede fabricar uno a su gusto.

    `vincular_a` = (usuario, versión de sesión) si se está vinculando desde Mi cuenta."""
    datos = {"tipo": "oauth", "prov": proveedor, "st": estado, "pkce": verificador}
    if vincular_a:
        datos |= {"sub": str(vincular_a[0]), "ver": vincular_a[1]}
    return _firmar(datos, 10)


def decodificar_estado_oauth(token: str) -> dict | None:
    return _verificar(token, "oauth", ["prov", "st", "pkce"])


def reto_pkce(verificador: str) -> str:
    """code_challenge S256 (RFC 7636): base64url sin relleno del SHA-256 del verificador."""
    resumen = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumen).rstrip(b"=").decode("ascii")


# --- Cifrado de los secretos TOTP ---


@lru_cache
def _aes() -> AESGCM:
    # MFA_CLAVE es texto de longitud libre: HKDF lo convierte en una clave AES de 256 bits
    clave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"umbral-mfa-totp").derive(
        obtener_configuracion().mfa_clave.encode()
    )
    return AESGCM(clave)


def cifrar_secreto(secreto: str, usuario_id: int) -> str:
    # El id del usuario va como dato asociado: un secreto copiado a la fila de otra cuenta
    # no se descifra
    nonce = secrets.token_bytes(12)
    cifrado = _aes().encrypt(nonce, secreto.encode(), str(usuario_id).encode())
    return base64.urlsafe_b64encode(nonce + cifrado).decode("ascii")


def descifrar_secreto(guardado: str, usuario_id: int) -> str | None:
    try:
        crudo = base64.urlsafe_b64decode(guardado)
        return _aes().decrypt(crudo[:12], crudo[12:], str(usuario_id).encode()).decode()
    except (InvalidTag, ValueError):
        return None
