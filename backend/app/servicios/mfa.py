"""Verificación en dos pasos con TOTP (RFC 6238): alta, segundo factor y códigos de recuperación.

Garantías:
- El secreto se guarda cifrado (AES-GCM con MFA_CLAVE) y ligado a su usuario.
- Cada código TOTP vale una sola vez (anti-replay por paso de 30 s, con UPDATE atómico).
- Cinco fallos seguidos bloquean el segundo factor 15 minutos, cambie o no la IP.
- Cambiar el segundo factor exige reautenticarse: un access token robado no basta.
"""

import hmac
import time
from datetime import datetime, timedelta

import pyotp
import segno
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import obtener_configuracion
from app.errores import Conflicto, Invalido, NoAutenticado, Prohibido
from app.esquemas import MfaAlta
from app.modelos import (
    Usuario,
    a_utc,
    ahora,
    generar_codigo_invitacion,
    normalizar_codigo_invitacion,
)
from app.repositorios import RepositorioCodigosRecuperacion, RepositorioUsuarios
from app.seguridad import cifrar_secreto, descifrar_secreto, hashear_token, verificar_contrasena
from app.servicios.auditoria import auditar

EMISOR = "Kaelum Umbral"
_PERIODO = 30
_MAX_FALLOS = 5
_BLOQUEO = timedelta(minutes=15)
_NUM_CODIGOS = 10
_CODIGO_INCORRECTO = "Código incorrecto"
# Cuánto vale un login como prueba fresca para una cuenta sin contraseña
_REAUTENTICACION = timedelta(minutes=5)
REAUTENTICACION_CADUCADA = "Vuelve a iniciar sesión con tu proveedor para confirmar que eres tú"


def _instante() -> float:
    """Reloj del TOTP. Los tests lo sustituyen para generar códigos de pasos distintos."""
    return time.time()


def mfa_exigido(usuario: Usuario) -> bool:
    """Su rol obliga a tener MFA (personal del MSSP), lo tenga ya o no."""
    return obtener_configuracion().mfa_obligatorio_personal and usuario.es_personal


def mfa_por_activar(usuario: Usuario) -> bool:
    return mfa_exigido(usuario) and not usuario.mfa_activo


def _paso_valido(secreto: str, codigo: str) -> int | None:
    """El paso de 30 s al que corresponde el código, o None si no casa con ninguno."""
    if len(codigo) != 6 or not codigo.isdigit():
        return None
    totp = pyotp.TOTP(secreto)
    actual = int(_instante()) // _PERIODO
    # ±1 paso: tolera hasta 30 s de desfase entre el reloj del móvil y el del servidor
    for paso in (actual - 1, actual, actual + 1):
        if hmac.compare_digest(totp.generate_otp(paso), codigo):
            return paso
    return None


async def reautenticar(
    sesion: AsyncSession,
    usuario: Usuario,
    contrasena: str | None,
    ip: str | None,
    *,
    autenticado_en: datetime | None,
    codigo: str | None = None,
) -> None:
    """Exige una prueba fresca de identidad. Falla en cerrado: sin prueba, no pasa.

    - Con contraseña: la contraseña.
    - Sin contraseña (solo Google o GitHub): un código MFA, si lo tiene activo, o un login de
      hace menos de 5 minutos. Si no, un access token robado bastaría para vincular otra cuenta
      o activar un MFA del atacante y dejar fuera al dueño.
    """
    if usuario.tiene_contrasena:
        if contrasena is not None and verificar_contrasena(usuario.hash_contrasena, contrasena):
            return
        error: Invalido | Prohibido = Invalido("La contraseña no es correcta")
    else:
        if usuario.mfa_activo and codigo:
            await verificar_segundo_factor(sesion, usuario, codigo, ip)
            return
        if autenticado_en is not None and ahora() - a_utc(autenticado_en) <= _REAUTENTICACION:
            return
        error = Prohibido(REAUTENTICACION_CADUCADA)

    await auditar(
        sesion,
        accion="mfa_reautenticacion_fallida",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
    raise error


async def _nuevos_codigos(sesion: AsyncSession, usuario: Usuario) -> list[str]:
    # Mismo formato que el código de invitación: ~59 bits, sin caracteres ambiguos. Un hash
    # rápido basta con esa entropía y el límite de intentos
    codigos = [generar_codigo_invitacion() for _ in range(_NUM_CODIGOS)]
    await RepositorioCodigosRecuperacion(sesion).reemplazar(
        usuario.id, [hashear_token(c) for c in codigos]
    )
    return codigos


async def iniciar(
    sesion: AsyncSession,
    usuario: Usuario,
    contrasena: str | None,
    ip: str | None,
    autenticado_en: datetime | None,
) -> MfaAlta:
    if usuario.mfa_activo:
        raise Conflicto("La verificación en dos pasos ya está activa")
    await reautenticar(sesion, usuario, contrasena, ip, autenticado_en=autenticado_en)

    secreto = pyotp.random_base32()  # 160 bits, lo que recomienda la RFC 4226
    # Queda pendiente: el MFA no cuenta hasta que el usuario demuestra que su app genera códigos
    usuario.mfa_pendiente = cifrar_secreto(secreto, usuario.id)
    await sesion.commit()

    uri = pyotp.TOTP(secreto).provisioning_uri(name=usuario.email, issuer_name=EMISOR)
    matriz = segno.make(uri, error="m").matrix
    filas = ["".join("1" if modulo else "0" for modulo in fila) for fila in matriz]
    return MfaAlta(secreto=secreto, uri=uri, qr=filas)


async def activar(sesion: AsyncSession, usuario: Usuario, codigo: str, ip: str | None) -> list[str]:
    if usuario.mfa_activo:
        raise Conflicto("La verificación en dos pasos ya está activa")
    if not usuario.mfa_pendiente:
        raise Conflicto("Empieza de nuevo la activación")

    secreto = descifrar_secreto(usuario.mfa_pendiente, usuario.id)
    paso = _paso_valido(secreto, codigo.strip()) if secreto else None
    if paso is None:
        await auditar(
            sesion,
            accion="mfa_alta_fallida",
            recurso="usuario",
            usuario_id=usuario.id,
            recurso_id=usuario.id,
            ip=ip,
        )
        await sesion.commit()
        raise Invalido(_CODIGO_INCORRECTO)

    usuario.mfa_secreto = usuario.mfa_pendiente
    usuario.mfa_pendiente = None
    usuario.mfa_ultimo_paso = paso  # el código de la activación tampoco se puede reutilizar
    codigos = await _nuevos_codigos(sesion, usuario)
    await auditar(
        sesion,
        accion="activar_mfa",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
    return codigos


async def verificar_segundo_factor(
    sesion: AsyncSession, usuario: Usuario, codigo: str, ip: str | None
) -> None:
    """Valida un código TOTP o de recuperación. Si falla, lo apunta y lanza NoAutenticado."""
    momento = ahora()
    usuarios = RepositorioUsuarios(sesion)
    if usuario.mfa_bloqueado_hasta and a_utc(usuario.mfa_bloqueado_hasta) > momento:
        raise NoAutenticado("Demasiados códigos incorrectos. Espera unos minutos")

    limpio = codigo.replace(" ", "").strip()
    secreto = descifrar_secreto(usuario.mfa_secreto, usuario.id) if usuario.mfa_secreto else None
    valido, via = False, "totp"
    if limpio.isdigit():
        paso = _paso_valido(secreto, limpio) if secreto else None
        valido = paso is not None and await usuarios.marcar_paso_mfa(usuario.id, paso)
    else:
        via = "recuperacion"
        valido = await RepositorioCodigosRecuperacion(sesion).consumir(
            usuario.id, hashear_token(normalizar_codigo_invitacion(limpio)), momento
        )

    if not valido:
        bloqueada = await usuarios.registrar_fallo_mfa(usuario.id, _MAX_FALLOS, momento + _BLOQUEO)
        await auditar(
            sesion,
            accion="mfa_fallido",
            recurso="usuario",
            usuario_id=usuario.id,
            recurso_id=usuario.id,
            ip=ip,
            detalle="bloqueado 15 min" if bloqueada else via,
        )
        await sesion.commit()
        raise NoAutenticado(_CODIGO_INCORRECTO)

    await usuarios.reiniciar_fallos_mfa(usuario.id)
    if via == "recuperacion":
        restantes = await RepositorioCodigosRecuperacion(sesion).disponibles(usuario.id)
        await auditar(
            sesion,
            accion="codigo_recuperacion_usado",
            recurso="usuario",
            usuario_id=usuario.id,
            recurso_id=usuario.id,
            ip=ip,
            detalle=f"quedan {restantes}",
        )


async def quitar(sesion: AsyncSession, usuario: Usuario) -> None:
    usuario.mfa_secreto = None
    usuario.mfa_pendiente = None
    usuario.mfa_ultimo_paso = None
    await RepositorioCodigosRecuperacion(sesion).borrar_de_usuario(usuario.id)
    await RepositorioUsuarios(sesion).reiniciar_fallos_mfa(usuario.id)


async def desactivar(
    sesion: AsyncSession, usuario: Usuario, contrasena: str | None, codigo: str, ip: str | None
) -> None:
    if not usuario.mfa_activo:
        raise Conflicto("La verificación en dos pasos no está activa")
    if mfa_exigido(usuario):
        raise Conflicto("Tu rol exige la verificación en dos pasos")
    # Contraseña (si la hay) Y código. Sin contraseña, el código es la prueba fresca
    if usuario.tiene_contrasena:
        await reautenticar(sesion, usuario, contrasena, ip, autenticado_en=None)
    await verificar_segundo_factor(sesion, usuario, codigo, ip)
    await quitar(sesion, usuario)
    await auditar(
        sesion,
        accion="desactivar_mfa",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()


async def regenerar_codigos(
    sesion: AsyncSession, usuario: Usuario, codigo: str, ip: str | None
) -> list[str]:
    if not usuario.mfa_activo:
        raise Conflicto("La verificación en dos pasos no está activa")
    await verificar_segundo_factor(sesion, usuario, codigo, ip)
    codigos = await _nuevos_codigos(sesion, usuario)
    await auditar(
        sesion,
        accion="regenerar_codigos_mfa",
        recurso="usuario",
        usuario_id=usuario.id,
        recurso_id=usuario.id,
        ip=ip,
    )
    await sesion.commit()
    return codigos
